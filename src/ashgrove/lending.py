"""Lending: Ashgrove Credit's consumer loan applications.

Credit decisions are a high-risk use under the EU AI Act. The rule is built into
the service: software may add a recommendation, but only a named human loan
officer can record a decision, and a decline must carry a reason.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .common import Caller, Store, audit, create_app, get_caller, require_roles
from .crm import N_CUSTOMERS
from .synth import days_ago, iso

SCHEMA = """
CREATE TABLE applications (
  id TEXT PRIMARY KEY, customer_id TEXT, amount_eur INTEGER, term_months INTEGER,
  monthly_income_eur INTEGER, existing_debt_eur INTEGER, employment_status TEXT,
  credit_history_months INTEGER, purpose TEXT, status TEXT, created_at TEXT
);
CREATE TABLE recommendations (
  id TEXT PRIMARY KEY, application_id TEXT, recommendation TEXT, rationale TEXT,
  model TEXT, actor TEXT, created_at TEXT
);
CREATE TABLE decisions (
  id TEXT PRIMARY KEY, application_id TEXT, decision TEXT, reason TEXT,
  decided_by TEXT, via TEXT, created_at TEXT
);
"""
N_APPS = 150


def seed(conn, rng):
    for i in range(N_APPS):
        income = rng.choice(range(1400, 7200, 100))
        conn.execute(
            "INSERT INTO applications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"L-{3001 + i}",
                f"C-{1001 + rng.randrange(N_CUSTOMERS)}",
                rng.choice(range(1000, 25001, 500)),
                rng.choice([12, 24, 36, 48, 60]),
                income,
                rng.choice([0, 0, 500, 1500, 4000, 9000]),
                rng.choices(["employed", "self-employed", "student", "retired", "unemployed"], [60, 15, 8, 10, 7])[0],
                rng.randint(0, 240),
                rng.choice(["car", "home improvement", "education", "debt consolidation", "furniture"]),
                rng.choices(["received", "in_review", "approved", "declined"], [35, 30, 20, 15])[0],
                iso(days_ago(rng, 0, 90)),
            ),
        )


store = Store("lending", SCHEMA, seed)
app = create_app(
    "lending", "Ashgrove Credit (lending)", "Loan applications. High-risk: humans decide, software may only recommend.", store
)


@app.get("/v1/applications", tags=["applications"])
def list_applications(
    status: str | None = None, limit: int = 20, caller: Caller = Depends(require_roles("loan_officer", "auditor"))
):
    sql, args = "SELECT * FROM applications", []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    return store.all(sql + " ORDER BY created_at DESC LIMIT ?", [*args, min(limit, 100)])


@app.get("/v1/applications/{app_id}", tags=["applications"])
def get_application(app_id: str, caller: Caller = Depends(require_roles("loan_officer", "auditor"))):
    row = store.one("SELECT * FROM applications WHERE id = ?", (app_id.upper(),))
    if not row:
        raise HTTPException(404, f"No application {app_id}")
    row["recommendations"] = store.all("SELECT * FROM recommendations WHERE application_id = ?", (row["id"],))
    row["decisions"] = store.all("SELECT * FROM decisions WHERE application_id = ?", (row["id"],))
    return row


class RecommendationIn(BaseModel):
    recommendation: str = Field(pattern="^(approve|decline|refer)$")
    rationale: str = Field(min_length=20)
    model: str = "unspecified"


@app.post("/v1/applications/{app_id}/recommendations", tags=["applications"], status_code=201)
def recommend(app_id: str, body: RecommendationIn, request: Request, caller: Caller = Depends(require_roles("loan_officer"))):
    """Software (or a person) records a recommendation with a rationale. This never changes the status."""
    if not store.one("SELECT id FROM applications WHERE id = ?", (app_id.upper(),)):
        raise HTTPException(404, f"No application {app_id}")
    rid = f"REC-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO recommendations VALUES (?,?,?,?,?,?,datetime('now'))",
            (rid, app_id.upper(), body.recommendation, body.rationale, body.model, caller.actor),
        )
    audit(store, request, caller, "recommend", app_id.upper(), body.model_dump())
    return {"recommendation_id": rid}


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|declined)$")
    reason: str = ""


@app.post("/v1/applications/{app_id}/decision", tags=["applications"])
def decide(app_id: str, body: DecisionIn, request: Request, caller: Caller = Depends(require_roles("loan_officer"))):
    """Only a named human may decide (the caller must act on behalf of a person)."""
    if not caller.on_behalf_of:
        raise HTTPException(403, "Credit decisions need a named human loan officer (on_behalf_of). Software may only recommend.")
    if body.decision == "declined" and len(body.reason.strip()) < 20:
        raise HTTPException(422, "A decline needs a reason of at least 20 characters the applicant can understand.")
    row = store.one("SELECT status FROM applications WHERE id = ?", (app_id.upper(),))
    if not row:
        raise HTTPException(404, f"No application {app_id}")
    if row["status"] in ("approved", "declined"):
        raise HTTPException(409, f"Application already {row['status']}")
    did = f"DEC-{uuid.uuid4().hex[:8]}"
    with store.connect() as c:
        c.execute(
            "INSERT INTO decisions VALUES (?,?,?,?,?,?,datetime('now'))",
            (did, app_id.upper(), body.decision, body.reason, caller.on_behalf_of, caller.actor),
        )
        c.execute("UPDATE applications SET status = ? WHERE id = ?", (body.decision, app_id.upper()))
    audit(store, request, caller, "decide", app_id.upper(), body.model_dump())
    return {"decision_id": did, "status": body.decision}


@app.get("/v1/applications/{app_id}/explanation", tags=["applications"])
def explanation(app_id: str, caller: Caller = Depends(get_caller)):
    """What the applicant is entitled to see: the decision and its reason."""
    d = store.one(
        "SELECT decision, reason, created_at FROM decisions WHERE application_id = ? ORDER BY created_at DESC", (app_id.upper(),)
    )
    if not d:
        raise HTTPException(404, "No decision yet")
    return d
