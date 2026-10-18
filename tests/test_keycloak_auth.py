"""AUTH_MODE=keycloak: validate real RS256 tokens against a local JWKS endpoint."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from conftest import client
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://localhost:8080/realms/ashgrove"


@pytest.fixture
def keycloak(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})
    body = json.dumps({"keys": [jwk]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    from ashgrove import common

    monkeypatch.setattr(common, "_jwks", common._JWKS())
    monkeypatch.setenv("AUTH_MODE", "keycloak")
    monkeypatch.setenv("KEYCLOAK_ISSUER", ISSUER)
    monkeypatch.setenv("KEYCLOAK_JWKS_URL", f"http://127.0.0.1:{server.server_port}/certs")

    def token(**claims):
        base = {"iss": ISSUER, "exp": int(time.time()) + 300, "iat": int(time.time())}
        return jwt.encode({**base, **claims}, key, algorithm="RS256", headers={"kid": "test-key"})

    yield token
    server.shutdown()


def test_missing_and_bad_tokens_are_rejected(keycloak):
    c = client("orders")
    assert c.get("/v1/orders").status_code == 401
    assert c.get("/v1/orders", headers={"authorization": "Bearer nonsense"}).status_code == 401
    expired = keycloak(azp="ashgrove-agent", exp=int(time.time()) - 10)
    assert c.get("/v1/orders", headers={"authorization": f"Bearer {expired}"}).status_code == 401


def test_service_account_cannot_decide_credit_but_user_token_can(keycloak):
    from ashgrove import lending

    app_id = lending.store.one("SELECT id FROM applications WHERE status='in_review'")["id"]
    c = client("lending")
    sa = keycloak(azp="credit-agent", preferred_username="service-account-credit-agent", realm_access={"roles": ["loan_officer"]})
    r = c.post(f"/v1/applications/{app_id}/decision", json={"decision": "approved"}, headers={"authorization": f"Bearer {sa}"})
    assert r.status_code == 403
    user = keycloak(azp="ashgrove-agent", preferred_username="lena", realm_access={"roles": ["loan_officer"]})
    r = c.post(f"/v1/applications/{app_id}/decision", json={"decision": "approved"}, headers={"authorization": f"Bearer {user}"})
    assert r.json()["status"] == "approved"
    log = c.get(
        "/admin/audit",
        headers={"authorization": f"Bearer {keycloak(azp='x', preferred_username='ruth', realm_access={'roles': ['auditor']})}"},
    ).json()
    assert log[0]["actor"] == "ashgrove-agent" and log[0]["on_behalf_of"] == "lena"


def test_roles_come_from_the_token_not_headers(keycloak):
    c = client("helpdesk")
    t = keycloak(
        azp="ashgrove-agent", preferred_username="service-account-ashgrove-agent", realm_access={"roles": ["support_agent"]}
    )
    r = c.get("/internal/integration-tokens", headers={"authorization": f"Bearer {t}", "x-roles": "it_admin"})
    assert r.status_code == 403
