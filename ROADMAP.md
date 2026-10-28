# Roadmap — next semester (6 months)

**Goal:** turn Agile CodeBoard from a strong final-year project into a production-grade, world-class project-intelligence platform.

**Assumptions:** 4 people, 12–15 hours/week each, two-week sprints, one shared staging environment. Every month ends with a demo, a written evaluation note and a deployable release.

**Definition of world-class for this project**

- Reliable: clear SLOs, health checks, backups, graceful degradation when the ML service is down.
- Trustworthy: calibrated and explainable predictions, measured acceptance, fairness review and an audit trail.
- Secure: no high/critical dependency findings, signed webhooks, SSO/2FA, rate limits and least-privilege access.
- Usable: WCAG 2.2 AA, responsive/mobile, onboarding, keyboard-first workflows and a coherent design system.
- Measurable: real datasets, backtests, ablations, a user study and published metrics.
- Extensible: documented APIs, webhooks, plugin/event model and a reproducible one-command deployment.

---

## Current baseline

Already implemented:

- PHP 8.5.12 / Fat-Free application, MySQL 8 and SQLite.
- FastAPI ML sidecar with internal-token auth and OpenAPI docs.
- Calibrated late-risk model, explanations, model quality page and walk-forward backtesting.
- Monte Carlo sprint forecasting with what-if scenarios.
- Assignee recommendations and a CP-SAT optimizer with fairness, baseline/lift and apply flow.
- Command center, sprint timeline, grounded assistant, in-app notifications, duplicate detection and GitHub webhook linking.
- Docker Compose, demo data, CI, PHPCS/PHPStan/PHPUnit, Ruff/pytest and a clean Composer audit.

Known gaps this roadmap closes:

- Duplicate detection is TF-IDF, not embedding-based.
- The assistant is deterministic; it is not an LLM-backed copilot with tool use and evals.
- GitHub support is webhook-only; no GitHub App, GitLab, Slack/Teams or DORA dashboard.
- No real-time collaboration, presence or offline-first behavior.
- No multi-tenancy, SSO, SCIM, 2FA/rate limiting or audit-log UI.
- Legacy analytics still uses a MySQL-to-SQLite compatibility bridge.
- Limited load testing, observability, accessibility testing and real-world evaluation.

---

## Month 1 — Quality foundation and real data

**Theme:** make the current system measurable, observable and trustworthy before adding more surface area.

### Workstreams

- **Real dataset:** collect or construct an anonymized dataset of 1,500+ closed tasks (public Jira/GitHub issues plus consented demo data). Document schema, consent and retention.
- **Evaluation harness:** rerun calibration, walk-forward backtesting and ablations on the real dataset. Report AUC, Brier, ECE, precision@10%, coverage and rank stability.
- **MLOps:** move training to a queued worker; add model registry versions, dataset hashes, drift metrics and a promotion gate. Keep the last good model active on failure.
- **Observability:** structured logs with request IDs across PHP → FastAPI; OpenTelemetry traces; Sentry (or equivalent); dashboards for latency, error rate, DB pool, queue depth and model latency.
- **Queue:** Redis-backed worker for training, webhook processing, notifications and forecast jobs; retries, dead-letter queue and idempotency.
- **Testing baseline:** raise backend coverage to 60% and add Playwright smoke tests for login, issue CRUD, forecast, optimizer, notifications and assistant.
- **Accessibility audit:** keyboard navigation, focus states, contrast, ARIA labels, screen-reader pass on command center, task board and issue page.
- **Security:** threat model (STRIDE), dependency and container scanning, secret hygiene, rate-limit design and an incident runbook.

### Exit criteria

- Real-data evaluation report with confidence intervals.
- p95 API latency measured and documented.
- CI runs unit, integration, E2E smoke, lint, audit and Docker build.
- Accessibility issues triaged with a prioritized fix list.

---

## Month 2 — Real-time collaboration and a GitHub App

**Theme:** make the product feel alive and integrate with how engineering teams actually work.

### Workstreams

- **Real-time board:** Mercure/SSE or WebSocket events for issue create/update/move/comment; presence avatars; reconnect and backoff.
- **Conflict handling:** use `issue.version` for optimistic concurrency; return `409` with the current state; idempotency keys for drag-and-drop; Playwright two-client conflict test.
- **Activity feed:** live sprint activity, “someone is editing” indicators and notification streaming.
- **Offline/PWA:** installable manifest, service worker, offline draft queue for comments/issues, background sync and conflict prompts.
- **GitHub App:** installation flow, least-privilege tokens, webhook signature verification, repository mapping and PR/commit linking. Add GitLab webhook parity.
- **DORA dashboard:** deployment frequency, lead time, change failure rate and MTTR from release/deployment events; label proxies honestly where data is missing.
- **Slack/Teams:** outbound notifications for assignments, sprint risk and PR links; slash-command or link-unfurl stretch goal.

### Exit criteria

- Two browsers see a card move in under one second on LAN.
- No lost updates in the concurrent-edit test.
- GitHub App installs on a test repo and links a PR to an issue.
- DORA page populated from simulated deployment events.

---

## Month 3 — Intelligence v2: embeddings, LLM copilot and drift

**Theme:** move from a rule-based assistant to a grounded AI copilot with measurable quality.

### Workstreams

- **Embeddings:** sentence-transformer embeddings stored in Qdrant; hybrid BM25 + vector search; duplicate detection evaluated with precision@5 on labeled pairs.
- **LLM copilot:** RAG over issues, comments, sprints and forecasts; tool calls for search, create/update issue, assign, forecast and explain. Permissions enforced in PHP, never trusted to the model.
- **Guardrails:** confirmation previews for writes, prompt-injection defenses, PII redaction, allowlisted tools and an audit trail for every action.
- **Evaluation:** golden set of 100 questions/actions; metrics for groundedness, answer relevance, tool-call accuracy, unauthorized-action rate and latency; CI regression on a small suite.
- **Explainability v2:** SHAP for tree models, counterfactuals (“move the due date +2 days → risk 31%”), global feature importance and sensitivity analysis.
- **Fairness:** score sensitivity to weights, rank stability under perturbation, minimum-sample rules, override/appeal workflow and an ethics note.
- **Drift:** population stability index on features, calibration drift, outcome drift and alerts on the command center.
- **Legacy analytics:** replace the SQLite mirror with a native MySQL analytics pipeline; remove the compatibility bridge.

### Exit criteria

- Duplicate detection precision@5 measured on a labeled set.
- Copilot golden-set accuracy ≥ 90% for tool calls and zero unauthorized writes in tests.
- Every prediction has an explanation and a model/dataset version.
- Legacy analytics runs natively on MySQL without a mirror.

---

## Month 4 — Enterprise readiness

**Theme:** make the platform safe and appealing for real organizations.

### Workstreams

- **Workspaces / multi-tenancy:** `workspace`, `workspace_user`, workspace-scoped data and global query filters; migration for existing data; cross-tenant isolation test suite.
- **SSO:** OIDC (Keycloak/Authentik) and optional SAML; JIT provisioning; SCIM stretch goal.
- **2FA and sessions:** TOTP with recovery codes, session rotation, token hashing at rest, idle timeout, optional IP/UA binding.
- **RBAC:** admin/manager/user/client roles per workspace; permission matrix tests; API scopes.
- **Audit log UI:** actor, action, entity, before/after, IP/UA, filters and tamper-evident hash chain.
- **Rate limits:** login, API, assistant, search and webhook endpoints; per-key quotas and 429 responses with retry-after.
- **Data governance:** export, delete/retention policy, consent notes and anonymization tooling.
- **API platform:** OpenAPI spec, versioning policy, API keys with scopes, webhook subscriptions and signed delivery.

### Exit criteria

- Tenant isolation suite green across every route.
- SSO login works end-to-end; 2FA enforced for admins.
- Audit log captures all privileged actions.
- API docs published and usable without reading source code.

---

## Month 5 — Scale, performance and product polish

**Theme:** make it fast, resilient and pleasant to use every day.

### Workstreams

- **Performance:** query profiling, indexes, caching (predictions, analytics, permissions), pagination and background jobs; load test with k6 at 10× demo scale.
- **SLOs:** p95 CRUD < 300ms, forecast < 2s, optimizer < 5s, assistant < 5s, uptime target 99.9% in staging.
- **Reliability:** backups, restore drills, migration rollback tests, circuit breakers and degraded-mode behavior when ML/Redis is down.
- **Design system:** tokens, components, empty/error/loading states, dark mode, density options and consistent tables/forms.
- **Mobile/PWA:** responsive task board, issue editing, notifications and assistant; touch-friendly drag-and-drop.
- **Productivity:** command palette, keyboard shortcuts, saved filters, bulk actions, onboarding checklist and contextual help.
- **Dashboards:** configurable widgets, personal dashboard, team dashboard and saved report exports (CSV/PDF).
- **i18n:** complete translation coverage, RTL check and locale-aware dates/numbers.

### Exit criteria

- Load test meets the SLOs with no errors at target concurrency.
- Restore drill succeeds from a backup.
- WCAG 2.2 AA audit passes for critical flows.
- Mobile task-board and assistant are usable without horizontal scrolling.

---

## Month 6 — Validation, documentation and v1.0

**Theme:** prove the value and make the project easy to adopt, evaluate and extend.

### Workstreams

- **User study:** 15–20 participants, task-based usability test, SUS, suggestion acceptance, trust/explainability questions and a short qualitative interview.
- **Field evaluation:** shadow deployment with one real team if possible; measure forecast accuracy, acceptance and time-to-plan.
- **Research write-up:** methodology, dataset, baselines, ablations, calibration, fairness and limitations; target a student symposium or arXiv preprint.
- **Security review:** external penetration test or structured self-assessment; fix high/critical findings; publish a security policy.
- **Docs site:** installation, admin guide, API reference, model cards, architecture decision records, plugin SDK and troubleshooting.
- **Release engineering:** versioned releases, changelog automation, signed images, upgrade guide and a one-command demo.
- **Demo package:** 5-minute video, seeded demo, slide deck, evaluation dashboard and reproducible benchmark.
- **v1.0 release:** freeze features, run the full matrix (PHP/MySQL/SQLite, Python, Docker, E2E), tag and publish.

### Exit criteria

- SUS ≥ 80 and task success ≥ 90% in the user study.
- Forecast calibration and acceptance metrics reported with confidence intervals.
- No open high/critical security findings.
- v1.0 tagged, documented and reproducibly deployable.

---

## Six-month timeline at a glance

| Month | Theme | Flagship deliverable |
|---|---|---|
| 1 | Foundation and real data | Real-data evaluation + observability/queue |
| 2 | Real-time and GitHub App | Live board + GitHub App + DORA dashboard |
| 3 | Intelligence v2 | Embeddings, LLM copilot, SHAP/counterfactuals |
| 4 | Enterprise readiness | Workspaces, SSO/2FA, audit UI, API platform |
| 5 | Scale and polish | SLOs, load tests, design system, PWA |
| 6 | Validation and release | User study, docs, security review, v1.0 |

---

## World-class scorecard

| Dimension | Target by end of semester |
|---|---|
| Reliability | 99.9% staging uptime; graceful ML degradation; restore drill passed |
| Performance | CRUD p95 < 300ms; forecast < 2s; optimizer < 5s; assistant < 5s |
| Security | No high/critical dependency or pentest findings; SSO + 2FA; rate limits |
| Privacy | Tenant isolation; export/delete; retention policy; PII redaction |
| Accessibility | WCAG 2.2 AA for login, issue, board, command center and assistant |
| Testing | 80% backend coverage; 70% frontend; E2E critical paths; load tests |
| ML quality | Calibrated, backtested, explainable; ECE < 0.05 on holdout |
| Copilot | ≥ 90% tool accuracy; zero unauthorized writes; citations on every answer |
| UX | SUS ≥ 80; task success ≥ 90%; mobile/PWA usable |
| Operations | One-command deploy; backups; traces; dashboards; upgrade guide |
| Documentation | Docs site, API reference, model cards, ADRs, plugin SDK |

---

## Priorities and cut lines

**P0 — must ship**

- Real-data evaluation and calibration.
- Real-time board with conflict handling.
- GitHub App and DORA dashboard.
- LLM copilot with evals and guardrails.
- Workspaces + SSO + audit log.
- Load tests, backups and observability.
- Accessibility pass and user study.
- v1.0 docs and release.

**P1 — should ship**

- GitLab parity, Slack/Teams notifications.
- Offline/PWA draft queue.
- Command palette and saved filters.
- Configurable dashboards and report exports.
- SCIM and SAML.
- Model drift alerts.

**P2 — stretch**

- Plugin marketplace/SDK.
- Mobile native app.
- Federated/privacy-preserving benchmarks.
- Advanced causal analysis and simulation.
- Billing/subscription.

If time slips, protect P0 and cut P2 first. Do not cut testing, security, accessibility or the user study — they are the difference between a demo and a world-class product.

---

## Team allocation

| Role | Focus |
|---|---|
| ML/backend engineer | risk, forecasting, optimizer, copilot, evals, drift |
| Platform engineer | real-time, queue, GitHub App, observability, performance |
| Product/full-stack engineer | command center, timeline, notifications, design system, PWA |
| QA/DevOps engineer | E2E, load, security, CI/CD, backups, release |
| All | user study, documentation, demo, paper |

Weekly cadence: Monday planning, Wednesday integration check, Friday demo; two-week release candidate; monthly retrospective.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope creep | P0/P1/P2 cut lines; monthly release gate |
| Real data unavailable | Use public Jira/GitHub datasets + consented demo data; document limitations |
| LLM cost/latency | Local model option, caching, evaluation and a deterministic fallback |
| Multi-tenancy leakage | Global query scopes + isolation tests on every route |
| GitHub permissions | Use a GitHub App on a test org; least-privilege tokens |
| Real-time complexity | Start with Mercure/SSE, fall back to polling; feature flag |
| Performance regressions | Load tests in CI, query budgets, caching |
| Team availability | Pair on P0, cut P2, keep a weekly integration branch |

---

## What not to build

- A generic chat app, video calls or document editing.
- A second Jira clone; stay focused on intelligence and workflow.
- Custom billing before the core platform is stable.
- A mobile native app before the PWA is excellent.
- Features that cannot be measured or evaluated.

---

**Roadmap prepared for the next semester. Added by Vedant Chalke.**
