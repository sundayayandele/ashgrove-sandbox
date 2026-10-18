# Ashgrove Group: company profile

Ashgrove Group is fictional. Use this profile for discovery interviews, design reviews and role-play.

## At a glance

| | |
|---|---|
| Headquarters | Utrecht, the Netherlands |
| Markets | Netherlands, Germany, United Kingdom, Nigeria (Lagos, Abuja), South Africa (Johannesburg, Cape Town) |
| Staff | About 2,400 |
| Divisions | **Ashgrove Retail** (online home-office equipment), **Ashgrove Credit** (consumer loans up to EUR 25,000), **Ashgrove Logistics** (warehousing and delivery) |
| Customers | About 1.1 million active; the sandbox holds 200 of them |
| Regulation | GDPR, EU AI Act (credit and hiring are high-risk), consumer credit rules, PCI DSS for payments |

## Systems

| System | Sandbox service | Age and quirks |
|---|---|---|
| Customer records | `crm` | Modern, but contact details are scattered across notes |
| Order management | `orders` | 15 years old. REST facade added in 2022; warehouse tools still call the XML endpoint |
| Helpdesk | `helpdesk` | Public contact form feeds straight into the ticket queue |
| Loan origination | `lending` | Rules engine plus manual review by loan officers |
| Applicant tracking | `hr` | Recruiters screen by hand; about 300 applications a week |
| Policy wiki | `docs` | Owners update pages, but old versions stay online |
| Identity | Keycloak (in production: a corporate IdP) | Staff SSO; no agent identities yet |
| Platform | Kubernetes in two regions, OpenShift on-prem for Ashgrove Credit | Credit data may not leave the on-prem cluster |

## Where it hurts today

- The support backlog averages **3 working days**. 60% of tickets are "where is my order", refunds or returns.
- Refund errors cost about EUR 180,000 last year: wrong amounts, refunds on undelivered orders, refunds under the old 2023 policy.
- Loan officers spend 40 minutes per application gathering facts before they can decide.
- Recruiters receive 300 applications a week for 6 open roles.
- Two AI pilots stalled last year: one leaked a customer list in a demo, the other could not pass the security review.

## What the board wants in 12 months

1. Support backlog under 1 day, without losing satisfaction.
2. No AI decision on credit or hiring without a named human.
3. Every AI agent traceable: who it acted for, what it did, what it cost.
4. Credit data stays on the on-prem OpenShift cluster.

## Stakeholders (for FDE role-play)

| Name | Role | Cares about | Red line |
|---|---|---|---|
| Tunde Balogun | Head of Customer Service | Backlog, satisfaction, refund accuracy | "No refund over EUR 100 without one of my leads" |
| Ruth Khumalo | Data Protection Officer | GDPR, erasure, data minimisation | "No bulk export of customer contact details, ever" |
| Ade Okafor | IT Operations Lead | Uptime, on-call load, who supports it after you leave | "If it isn't in our IdP and our monitoring, it doesn't go live" |
| Nadia Visser | CISO | Prompt injection, secrets, supplier risk | "No agent gets admin credentials, demo or not" |
| Lena Fischer | Chief Credit Officer | Affordability, regulator scrutiny | "Software recommends. My officers decide." |
| James Patel | Head of People | Fair hiring, recruiter time | "First screening is name-blind" |
| Pieter Botha | CFO | Cost per resolved case, payback | "Show me cost per outcome, not cost per call" |
