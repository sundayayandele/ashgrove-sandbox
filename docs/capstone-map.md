# Capstone map

Which parts of the sandbox each of the 36 capstones uses. **Deploy** shows the default target: Compose for beginner projects, Kubernetes or OpenShift from intermediate up.

Levels: B = beginner, I = intermediate, A = advanced, E = expert.

## Architects

| # | Lvl | Capstone | Sandbox parts | Deploy |
|---|---|---|---|---|
| A1 | B | Agent or not? Five use cases through the build ladder | company profile, all services as context | Compose |
| A2 | B | Single-agent reference architecture for refunds | orders, docs | Compose |
| A3 | B | Tool permission catalogue and approval matrix | orders approvals, lending and hr human-decision rules | Compose |
| A4 | I | Memory and data architecture with erasure flow | crm, helpdesk, orders erase endpoints | Kubernetes |
| A5 | I | Model gateway with fallbacks and cost caps | chaos knobs, observability | Kubernetes |
| A6 | I | Observability and eval reference architecture | observability profile, audit logs with trace ids | Kubernetes |
| A7 | A | Multi-agent hiring assistant design | hr (name-blind view, evidence rule) | Kubernetes |
| A8 | A | Agent threat model (OWASP Agentic Top 10) | planted injections, fake tokens, over-privileged client | Kubernetes |
| A9 | A | Agent identity architecture | Keycloak realm, token exchange, audit actor and on_behalf_of | OpenShift |
| A10 | E | MCP and A2A integration architecture | every service as a tool source | OpenShift |
| A11 | E | EU AI Act evidence architecture for credit | lending (recommend vs decide, explanations), audit | OpenShift |
| A12 | E | Enterprise agent platform blueprint | everything | OpenShift |

## AI engineers

| # | Lvl | Capstone | Sandbox parts | Deploy |
|---|---|---|---|---|
| E1 | B | Refund desk agent | orders, docs | Compose |
| E2 | B | Policy Q&A with citations | docs (superseded and bereavement traps) | Compose |
| E3 | B | Reliability harness with pass^k | any service, chaos knobs | Compose |
| E4 | I | MCP server for the order system (TypeScript) | orders REST and XML | Kubernetes |
| E5 | I | Human approval loop | orders approvals, Mailpit | Kubernetes |
| E6 | I | Tracing and cost dashboards | observability profile | Kubernetes |
| E7 | A | Long-horizon migration agent | export CSVs and the legacy XML endpoint as the migration target | Kubernetes |
| E8 | A | Research orchestrator with sub-agents | docs, crm, helpdesk, orders | Kubernetes |
| E9 | A | Layered memory service with poisoning defences | helpdesk injections, crm erasure | Kubernetes |
| E10 | E | Cross-org A2A workflow (TypeScript) | orders plus an external "carrier" agent you build | OpenShift |
| E11 | E | Red-team range and guardrails | all planted material, over-privileged client | OpenShift |
| E12 | E | Production multi-agent system | everything, chaos, observability | OpenShift |

## Forward deployed engineers

| # | Lvl | Capstone | Sandbox parts | Deploy |
|---|---|---|---|---|
| F1 | B | Discovery sprint | company profile and stakeholders | none |
| F2 | B | Demo to pilot | orders, helpdesk, docs | Compose |
| F3 | B | Data onboarding | `ashgrove export` CSVs, docs | Compose |
| F4 | I | Legacy integration | orders XML endpoint | Kubernetes |
| F5 | I | Identity onboarding | Keycloak realm, AUTH_MODE=keycloak | Kubernetes |
| F6 | I | Security review pack | planted material, answer key, CISO red lines | Kubernetes |
| F7 | A | Sovereign / air-gapped deployment | OpenShift overlay plus a local model server | OpenShift |
| F8 | A | Pilot readout | audit logs, observability, CFO stakeholder | Kubernetes |
| F9 | A | Incident drill | chaos knobs, planted injections, reset | Kubernetes |
| F10 | E | Multi-system workflow | crm, helpdesk, orders, Mailpit | OpenShift |
| F11 | E | Regulated rollout (credit or hiring) | lending or hr, DPO and Chief Credit Officer stakeholders | OpenShift |
| F12 | E | Full engagement | everything | OpenShift |

## The production bar

A capstone counts as shipped when it has a running service, CI with an eval gate, OpenTelemetry traces and a cost view, secrets in a vault, auth on every endpoint, a runbook and a rollback path. It must run on both a paid model API and a local model.
