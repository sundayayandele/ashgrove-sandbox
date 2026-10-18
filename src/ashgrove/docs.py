"""Docs: Ashgrove's policy library, the source for RAG and grounding work.

It deliberately contains a superseded refund policy that contradicts the
current one, and one page with a hidden injection attempt.
"""

from __future__ import annotations

import re
from importlib import resources

import yaml
from fastapi import Depends, HTTPException

from .common import Caller, Store, create_app, get_caller


def _load() -> dict[str, dict]:
    out = {}
    for f in sorted(resources.files("ashgrove").joinpath("policies").iterdir()):
        if not f.name.endswith(".md"):
            continue
        text = f.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front)
        out[f.name.removesuffix(".md")] = {"slug": f.name.removesuffix(".md"), **meta, "body": body.strip()}
    return out


DOCS = _load()
store = Store("docs", "", lambda conn, rng: None)
app = create_app(
    "docs", "Ashgrove Policy Library", "Company policies. Check `status`: superseded versions must not be used.", store
)


@app.get("/v1/documents", tags=["documents"])
def list_documents(include_superseded: bool = True, caller: Caller = Depends(get_caller)):
    return [
        {k: d[k] for k in ("slug", "title", "version", "status", "effective_from", "owner")}
        for d in DOCS.values()
        if include_superseded or d["status"] == "current"
    ]


@app.get("/v1/documents/{slug}", tags=["documents"])
def get_document(slug: str, caller: Caller = Depends(get_caller)):
    if slug not in DOCS:
        raise HTTPException(404, f"No document {slug}")
    return DOCS[slug]


@app.get("/v1/search", tags=["documents"])
def search(q: str, limit: int = 5, caller: Caller = Depends(get_caller)):
    """Simple keyword search, so beginners have retrieval before building their own."""
    terms = [t for t in re.findall(r"\w+", q.lower()) if len(t) > 2]
    results = []
    for d in DOCS.values():
        paragraphs = [p.strip() for p in d["body"].split("\n\n") if p.strip()]
        for p in paragraphs:
            score = sum(p.lower().count(t) for t in terms)
            if score:
                results.append(
                    {
                        "slug": d["slug"],
                        "title": d["title"],
                        "status": d["status"],
                        "version": d["version"],
                        "score": score,
                        "snippet": p[:400],
                    }
                )
    return sorted(results, key=lambda r: -r["score"])[: min(limit, 20)]
