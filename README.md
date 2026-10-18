# Ashgrove Sandbox

**A fictional company you can run, break and deploy agents into.** Ashgrove Group is a mid-size retailer with a lending arm. This repository gives it working systems with seeded synthetic data, so architects, AI engineers and forward deployed engineers all practise on the same realistic estate.

It is the shared base for the 36 Agentic AI capstones (12 each for architects, AI engineers and FDEs). See [docs/capstone-map.md](docs/capstone-map.md).

| Service | What it is | Local port | Why it matters for agents |
|---|---|---|---|
| `crm` | Customer records | 8001 | Personal data, least-privilege reads, GDPR erasure |
| `orders` | 15-year-old order system: REST plus the original XML endpoint | 8002 | Legacy integration; refunds above EUR 100 need a support-lead approval the system enforces |
| `helpdesk` | Customer tickets and a public contact form | 8003 | Untrusted input, planted prompt injections, fake secrets |
| `lending` | Consumer loan applications | 8004 | EU AI Act high-risk: software recommends, only a named human decides |
| `hr` | Hiring pipeline | 8005 | High-risk: CV-cited screening notes, name-blind view, human decisions |
| `docs` | Policy library | 8006 | RAG and grounding, including a superseded policy that contradicts the current one |
| `mailpit` | Mail catcher | 8025 | Every email an agent sends lands here, never on the internet |
| `keycloak` | Identity provider | 8080 | Staff roles, agent clients, delegation (`identity` profile) |
| observability | OTel collector, Tempo, Prometheus, Grafana | 4317 / 3000 | Traces and metrics for your agents (`observability` profile) |

Every service has OpenAPI docs at `/docs`, plus `/healthz`, `/readyz`, `/metrics`, an audit log at `/admin/audit` and `POST /admin/reset`.

## Three ways to run it

### 1. On your laptop, no Docker (fastest start)

```bash
pip install "ashgrove-sandbox @ git+https://github.com/sundayayandele/ashgrove-sandbox"
ashgrove dev
# crm http://127.0.0.1:8001/docs ... docs http://127.0.0.1:8006/docs
```

### 2. Docker Compose (beginner track)

```bash
git clone https://github.com/sundayayandele/ashgrove-sandbox && cd ashgrove-sandbox
cp .env.example .env
docker compose up -d                                   # services + mail catcher, no login
docker compose --profile identity up -d                # add Keycloak; set AUTH_MODE=keycloak in .env
docker compose --profile observability up -d           # add tracing and dashboards (Grafana on :3000)
```

### 3. Kubernetes or OpenShift (default for intermediate and expert capstones)

```bash
# Kubernetes with an NGINX ingress controller (kind, k3d, AKS, EKS, GKE)
kubectl apply -k deploy/k8s/overlays/kubernetes
# open http://crm.ashgrove.localtest.me/docs, http://keycloak.ashgrove.localtest.me, ...

# OpenShift: first replace CLUSTER_APPS_DOMAIN in deploy/k8s/overlays/openshift/config-patch.yaml
oc apply -k deploy/k8s/overlays/openshift
oc get routes -n ashgrove
```

Both overlays run every pod as non-root with dropped capabilities and a RuntimeDefault seccomp profile, so they fit OpenShift's `restricted-v2` SCC and Kubernetes Pod Security "restricted". Keycloak login is on by default (`AUTH_MODE=keycloak`). Change the Keycloak admin password in `deploy/k8s/base/kustomization.yaml` before sharing a cluster.

Manifests are generated: edit `deploy/k8s/generate.py`, then run `python deploy/k8s/generate.py`.

## Identity

With `AUTH_MODE=none` (beginner), services trust three headers so you can see the rules without running Keycloak:

```bash
curl -H "X-Actor: refund-agent" -H "X-Roles: support_agent" localhost:8001/v1/customers/C-1001
curl -H "X-Actor: portal" -H "X-On-Behalf-Of: tunde" -H "X-Roles: support_lead" ...
```

With `AUTH_MODE=keycloak`, roles come only from the token. The `ashgrove` realm contains:

| Who | Type | Roles |
|---|---|---|
| maria · tunde · lena · james · ade · ruth | Staff users (password `ashgrove-demo`) | support_agent · support_lead · loan_officer · recruiter · it_admin · auditor |
| `ashgrove-agent` | Agent client, least privilege | support_agent |
| `ashgrove-overprivileged-agent` | Agent client with every role, **deliberately unsafe** | all |
| `ashgrove-portal` | Browser login (PKCE) | as the user |

```bash
# Agent acting on its own (client credentials)
curl -s localhost:8080/realms/ashgrove/protocol/openid-connect/token \
  -d grant_type=client_credentials -d client_id=ashgrove-agent -d client_secret=ashgrove-agent-sandbox-secret

# Agent acting for Maria: exchange her token for one issued to the agent (standard token exchange)
curl -s localhost:8080/realms/ashgrove/protocol/openid-connect/token \
  -d grant_type=urn:ietf:params:oauth:grant-type:token-exchange \
  -d client_id=ashgrove-agent -d client_secret=ashgrove-agent-sandbox-secret \
  -d subject_token="$MARIA_TOKEN" -d requested_token_type=urn:ietf:params:oauth:token-type:access_token
```

The audit log records the agent as `actor` and the person as `on_behalf_of`. High-risk decisions in `lending` and `hr` are refused unless a named person is on the token. Token exchange needs Keycloak 26.2 or later; check your version's documentation if the exchange is refused. Secrets above are for the sandbox only.

## Built-in test material

The data includes traps on purpose. Instructors: see [docs/answer-key.md](docs/answer-key.md).

- Five helpdesk tickets and one policy page contain prompt-injection attempts.
- The helpdesk holds fake integration tokens that no support agent should be able to read.
- The policy library has a superseded refund policy and a "no bereavement discount" rule (the Air Canada lesson).
- Applicant records include names, so you can test name-blind screening.

## Practice knobs

| Variable | Effect |
|---|---|
| `CHAOS_ERROR_RATE=0.1` | 10% of requests fail with 503 |
| `CHAOS_LATENCY_MS=500` | add half a second to every request |
| `REFUND_AUTO_LIMIT_EUR=100` | the refund amount above which a lead must approve |
| `ASHGROVE_SEED=42` | change the generated data |

```bash
ashgrove reset            # re-create all seeded data
ashgrove export ./csv     # every table as CSV, for data-onboarding work
```

## Ground rules

- Everything is synthetic. Emails use `example.test`, phone numbers use a fictional range, tokens are fake.
- Attack only this sandbox. Never point the security exercises at real systems.
- The sandbox resets on restart (SQLite on an `emptyDir`), which keeps every learner's environment identical.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
python deploy/k8s/generate.py --check
```

## Licence

MIT, by Sunday Ayandele. Part of the Agentic AI programme alongside [agent-kit](https://github.com/sundayayandele/agent-kit) and the [agentic casebook](https://github.com/sundayayandele/agentic-casebook).
