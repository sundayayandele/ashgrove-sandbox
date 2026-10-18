"""Shared plumbing for every Ashgrove service.

Each service is a small FastAPI app that owns one SQLite database. This module
gives them all the same behaviour:

- Identity: AUTH_MODE=none trusts X-Actor / X-On-Behalf-Of headers (beginner);
  AUTH_MODE=keycloak requires a Keycloak bearer token and checks roles.
- Audit: every write is recorded with who did it, for whom, and the trace id.
- Chaos: CHAOS_ERROR_RATE and CHAOS_LATENCY_MS inject failures for resilience work.
- Operations: /healthz, /readyz, /metrics (Prometheus text) and POST /admin/reset.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

DATA_DIR = Path(os.getenv("ASHGROVE_DATA_DIR", "/tmp/ashgrove-data"))
SEED = int(os.getenv("ASHGROVE_SEED", "42"))


# --------------------------------------------------------------------------- identity


@dataclass
class Caller:
    """Who is calling. `actor` is the software or person making the request;
    `on_behalf_of` is the human the actor works for, if any."""

    actor: str = "anonymous"
    on_behalf_of: str | None = None
    roles: set[str] = field(default_factory=set)
    authenticated: bool = False


class _JWKS:
    """Caches the Keycloak signing keys."""

    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()

    def key_for(self, token: str):
        import jwt

        with self._lock:
            if self._client is None:
                issuer = os.environ["KEYCLOAK_ISSUER"].rstrip("/")
                jwks_url = os.getenv("KEYCLOAK_JWKS_URL", f"{issuer}/protocol/openid-connect/certs")
                self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)
        return self._client.get_signing_key_from_jwt(token).key


_jwks = _JWKS()


def auth_mode() -> str:
    return os.getenv("AUTH_MODE", "none").lower()


def get_caller(request: Request) -> Caller:
    if auth_mode() == "none":
        roles = {r.strip() for r in request.headers.get("x-roles", "").split(",") if r.strip()}
        return Caller(
            actor=request.headers.get("x-actor", "anonymous"),
            on_behalf_of=request.headers.get("x-on-behalf-of"),
            roles=roles,
        )

    import jwt

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required (AUTH_MODE=keycloak)")
    token = header.split(" ", 1)[1]
    try:
        claims = jwt.decode(
            token,
            _jwks.key_for(token),
            algorithms=["RS256"],
            issuer=os.environ["KEYCLOAK_ISSUER"].rstrip("/"),
            audience=os.getenv("KEYCLOAK_AUDIENCE") or None,
            options={"verify_aud": bool(os.getenv("KEYCLOAK_AUDIENCE"))},
        )
    except Exception as exc:  # signature, expiry, issuer
        raise HTTPException(401, f"Invalid token: {type(exc).__name__}") from exc
    client = claims.get("azp") or claims.get("client_id") or "unknown-client"
    user = claims.get("preferred_username")
    is_service_account = bool(user and user.startswith("service-account-"))
    roles = set(claims.get("realm_access", {}).get("roles", []))
    return Caller(
        actor=client if not is_service_account else user,
        on_behalf_of=None if is_service_account else user,
        roles=roles,
        authenticated=True,
    )


def require_roles(*allowed: str) -> Callable[[Caller], Caller]:
    """Endpoint guard. In AUTH_MODE=none it checks the X-Roles header, so beginners
    can see the rule without running Keycloak."""

    def check(caller: Caller = Depends(get_caller)) -> Caller:
        if allowed and not (caller.roles & set(allowed)):
            raise HTTPException(403, f"Requires one of the roles: {', '.join(allowed)}")
        return caller

    return check


# --------------------------------------------------------------------------- database


class Store:
    """One SQLite file per service, created and seeded on first use."""

    def __init__(self, name: str, schema: str, seed: Callable[[sqlite3.Connection, random.Random], None]):
        self.name = name
        self.schema = schema + AUDIT_SCHEMA
        self.seed = seed
        self.path = DATA_DIR / f"{name}.db"
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                self.path.unlink()
            conn = sqlite3.connect(self.path)
            conn.executescript(self.schema)
            self.seed(conn, random.Random(f"{SEED}:{self.name}"))
            conn.commit()
            conn.close()

    @contextmanager
    def connect(self):
        if not self.path.exists():
            self.reset()
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None


AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  on_behalf_of TEXT,
  action TEXT NOT NULL,
  target TEXT,
  details TEXT,
  trace_id TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def audit(store: Store, request: Request, caller: Caller, action: str, target: str, details: dict | None = None) -> None:
    traceparent = request.headers.get("traceparent", "")
    trace_id = traceparent.split("-")[1] if traceparent.count("-") >= 3 else None
    with store.connect() as c:
        c.execute(
            "INSERT INTO audit_log (ts, actor, on_behalf_of, action, target, details, trace_id) VALUES (?,?,?,?,?,?,?)",
            (now_iso(), caller.actor, caller.on_behalf_of, action, target, json.dumps(details or {}), trace_id),
        )


# --------------------------------------------------------------------------- app factory


def create_app(name: str, title: str, description: str, store: Store) -> FastAPI:
    app = FastAPI(title=title, description=description, version="0.1.0")
    counts: Counter[tuple[str, str, int]] = Counter()

    @app.middleware("http")
    async def chaos_and_metrics(request: Request, call_next):
        path = request.url.path
        operational = path in ("/healthz", "/readyz", "/metrics") or path.startswith("/admin")
        if not operational:
            latency = int(os.getenv("CHAOS_LATENCY_MS", "0"))
            if latency:
                time.sleep(latency / 1000)
            if random.random() < float(os.getenv("CHAOS_ERROR_RATE", "0")):
                counts[(request.method, path, 503)] += 1
                return JSONResponse({"detail": "Injected failure (CHAOS_ERROR_RATE)"}, status_code=503)
        response = await call_next(request)
        route = request.scope.get("route")
        counts[(request.method, getattr(route, "path", path), response.status_code)] += 1
        return response

    @app.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok", "service": name}

    @app.get("/readyz", tags=["ops"])
    def readyz():
        store.one("SELECT 1 AS ok")
        return {"status": "ready", "service": name, "auth_mode": auth_mode()}

    @app.get("/metrics", tags=["ops"], response_class=PlainTextResponse)
    def metrics():
        lines = [
            "# HELP ashgrove_requests_total Requests by method, route and status.",
            "# TYPE ashgrove_requests_total counter",
        ]
        for (method, route, status), n in sorted(counts.items()):
            lines.append(f'ashgrove_requests_total{{service="{name}",method="{method}",route="{route}",status="{status}"}} {n}')
        return "\n".join(lines) + "\n"

    @app.post("/admin/reset", tags=["ops"])
    def reset(caller: Caller = Depends(require_roles("it_admin"))):
        store.reset()
        return {"status": "reset", "service": name, "seed": SEED}

    @app.get("/admin/audit", tags=["ops"])
    def audit_log(limit: int = 100, caller: Caller = Depends(require_roles("auditor", "it_admin"))):
        return store.all("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (min(limit, 1000),))

    return app
