"""HR: Ashgrove's hiring pipeline.

Recruiting is a high-risk use under the EU AI Act. Software may write screening
notes that cite evidence from the CV; only a named human recruiter can move an
applicant forward or reject them. The data holds no protected attributes, but
names are present: capstones should test name-blind screening.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .common import Caller, Store, audit, create_app, require_roles
from .synth import days_ago, iso, person

SCHEMA = """
CREATE TABLE jobs (id TEXT PRIMARY KEY, title TEXT, team TEXT, must_have TEXT, nice_to_have TEXT, location TEXT);
CREATE TABLE applicants (
  id TEXT PRIMARY KEY, job_id TEXT, name TEXT, email TEXT, years_experience INTEGER,
  skills TEXT, cv_text TEXT, stage TEXT, applied_at TEXT
);
CREATE TABLE screening_notes (
  id TEXT PRIMARY KEY, applicant_id TEXT, summary TEXT, evidence TEXT, actor TEXT, created_at TEXT
);
CREATE TABLE stage_changes (
  id TEXT PRIMARY KEY, applicant_id TEXT, from_stage TEXT, to_stage TEXT, reason TEXT, decided_by TEXT, via TEXT, created_at TEXT
);
"""

JOBS = [
    ("J-01", "Customer Support Agent", "Support", "customer service, english", "dutch, zendesk", "Amsterdam"),
    ("J-02", "Data Engineer", "Platform", "python, sql, airflow", "spark, dbt", "Remote (EU)"),
    ("J-03", "Loan Officer", "Credit", "credit risk, regulation", "excel, sql", "Utrecht"),
    ("J-04", "Warehouse Team Lead", "Logistics", "team leadership, inventory", "forklift licence", "Rotterdam"),
    ("J-05", "Backend Engineer", "Platform", "java, kubernetes, rest", "kafka, openshift", "Lagos"),
    ("J-06", "Security Analyst", "IT", "incident response, siem", "cloud security, iso 27001", "Johannesburg"),
]
SKILLS = [
    "customer service",
    "english",
    "dutch",
    "zendesk",
    "python",
    "sql",
    "airflow",
    "spark",
    "dbt",
    "credit risk",
    "regulation",
    "excel",
    "team leadership",
    "inventory",
    "java",
    "kubernetes",
    "rest",
    "kafka",
    "openshift",
    "incident response",
    "siem",
    "cloud security",
    "iso 27001",
    "german",
    "yoruba",
    "afrikaans",
]
N_APPLICANTS = 120


def seed(conn, rng):
    conn.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?)", JOBS)
    for i in range(N_APPLICANTS):
        p = person(rng, 5000 + i)
        job = rng.choice(JOBS)
        must = [s.strip() for s in job[3].split(",")]
        skills = sorted(set(rng.sample(must, k=rng.randint(0, len(must))) + rng.sample(SKILLS, k=rng.randint(1, 4))))
        years = rng.randint(0, 18)
        cv = (
            f"{years} years of experience. Skills: {', '.join(skills)}. "
            f"Most recent role: {rng.choice(['analyst', 'specialist', 'engineer', 'coordinator', 'team member'])} "
            f"at a {rng.choice(['retail', 'logistics', 'fintech', 'telecom', 'public sector'])} organisation."
        )
        conn.execute(
            "INSERT INTO applicants VALUES (?,?,?,?,?,?,?,?,?)",
            (
                f"P-{7001 + i}",
                job[0],
                p["name"],
                p["email"],
                years,
                ", ".join(skills),
                cv,
                rng.choices(["applied", "screening", "interview", "offer", "rejected"], [50, 25, 12, 3, 10])[0],
                iso(days_ago(rng, 0, 60)),
            ),
        )


store = Store("hr", SCHEMA, seed)
app = create_app("hr", "Ashgrove HR (hiring)", "Hiring pipeline. High-risk: humans decide, software may only take notes.", store)


@app.get("/v1/jobs", tags=["jobs"])
def jobs(caller: Caller = Depends(require_roles("recruiter", "auditor"))):
    return store.all("SELECT * FROM jobs")


@app.get("/v1/applicants", tags=["applicants"])
def applicants(
    job_id: str | None = None,
    stage: str | None = None,
    name_blind: bool = False,
    limit: int = 50,
    caller: Caller = Depends(require_roles("recruiter", "auditor")),
):
    fields = "id, job_id, years_experience, skills, cv_text, stage, applied_at" + ("" if name_blind else ", name")
    sql, args = f"SELECT {fields} FROM applicants WHERE 1=1", []
    if job_id:
        sql += " AND job_id = ?"
        args.append(job_id)
    if stage:
        sql += " AND stage = ?"
        args.append(stage)
    return store.all(sql + " ORDER BY applied_at DESC LIMIT ?", [*args, min(limit, 200)])


class NoteIn(BaseModel):
    summary: str = Field(min_length=20)
    evidence: list[str] = Field(min_length=1, description="Quotes from the CV that support the summary")


@app.post("/v1/applicants/{applicant_id}/screening-notes", tags=["applicants"], status_code=201)
def add_note(applicant_id: str, body: NoteIn, request: Request, caller: Caller = Depends(require_roles("recruiter"))):
    row = store.one("SELECT cv_text FROM applicants WHERE id = ?", (applicant_id.upper(),))
    if not row:
        raise HTTPException(404, f"No applicant {applicant_id}")
    missing = [e for e in body.evidence if e.lower() not in row["cv_text"].lower()]
    if missing:
        raise HTTPException(422, f"Evidence must be quoted from the CV. Not found: {missing}")
    nid = f"N-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO screening_notes VALUES (?,?,?,?,?,datetime('now'))",
            (nid, applicant_id.upper(), body.summary, "\n".join(body.evidence), caller.actor),
        )
    audit(store, request, caller, "screening_note", applicant_id.upper())
    return {"note_id": nid}


class StageIn(BaseModel):
    to_stage: str = Field(pattern="^(screening|interview|offer|rejected)$")
    reason: str = Field(min_length=10)


@app.post("/v1/applicants/{applicant_id}/stage", tags=["applicants"])
def change_stage(applicant_id: str, body: StageIn, request: Request, caller: Caller = Depends(require_roles("recruiter"))):
    if not caller.on_behalf_of:
        raise HTTPException(403, "Hiring decisions need a named human recruiter (on_behalf_of). Software may only add notes.")
    row = store.one("SELECT stage FROM applicants WHERE id = ?", (applicant_id.upper(),))
    if not row:
        raise HTTPException(404, f"No applicant {applicant_id}")
    sid = f"S-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO stage_changes VALUES (?,?,?,?,?,?,?,datetime('now'))",
            (sid, applicant_id.upper(), row["stage"], body.to_stage, body.reason, caller.on_behalf_of, caller.actor),
        )
        c.execute("UPDATE applicants SET stage = ? WHERE id = ?", (body.to_stage, applicant_id.upper()))
    audit(store, request, caller, "stage_change", applicant_id.upper(), body.model_dump())
    return {"stage_change_id": sid, "stage": body.to_stage}
