import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_data(tmp_path, monkeypatch):
    """Every test gets its own seeded data directory and default settings."""
    from ashgrove import common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    for var in ("AUTH_MODE", "CHAOS_ERROR_RATE", "CHAOS_LATENCY_MS", "REFUND_AUTO_LIMIT_EUR"):
        monkeypatch.delenv(var, raising=False)
    for name in ("crm", "orders", "helpdesk", "lending", "hr", "docs"):
        mod = importlib.import_module(f"ashgrove.{name}")
        mod.store.path = tmp_path / f"{mod.store.name}.db"
    yield


def client(name: str) -> TestClient:
    return TestClient(importlib.import_module(f"ashgrove.{name}").app)


AGENT = {"x-actor": "refund-agent", "x-roles": "support_agent"}
LEAD = {"x-actor": "portal", "x-on-behalf-of": "tunde", "x-roles": "support_lead"}
