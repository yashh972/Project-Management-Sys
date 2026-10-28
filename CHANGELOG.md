# Changelog

All notable changes to **Agile CodeBoard** in this session.

The project is a fork of [Phproject](https://github.com/Alanaktion/phproject). The intelligence layer, command center, timeline, notifications, duplicate detection, grounded assistant and GitHub integration were added by **Vedant Chalke**.

---

## [2026-10-28] — Project intelligence layer

### Added — platform foundation

- FastAPI inference service under `ml-service/` with health, version, metrics and OpenAPI endpoints.
- Internal-token authentication between the PHP application and the ML service.
- SQLAlchemy data layer that reads the same `config.php` as PHP and supports **MySQL and SQLite**.
- `Helper\Ml` HTTP client with timeouts, error handling and graceful fallback, replacing PHP `exec()` calls.
- Model registry (`model_run`) with model name, version, training rows, metrics, dataset hash and active flag.
- Docker Compose stack for the app, MySQL, ML service, Redis, Mercure, Qdrant, MailHog, app-dev and ml-dev.
- Multi-stage Docker images, PHP 8.5.12 runtime, one-command installer entrypoint and persistent config storage.
- Dual-dialect migrations (`db/26.10.*.sql` and `.sqlite.sql`) with engine-aware selection.
- CI for PHP 8.5 (MySQL + SQLite), Python lint/pytest and Docker image builds.

### Added — predictive intelligence

- Calibrated late-risk model trained on issue history and audit fields.
- Time-aware features: planned hours, priority, bug flag, allowed window, queue time, pressure, activation day, owner trailing late rate and owner load.
- Calibrated probabilities with sigmoid calibration and expanding-window validation.
- Per-issue explanations rendered as a visible **“Why this risk?”** panel with impact bars.
- Cycle-time estimates (P50/P85/P95) from activation-to-close history.
- Model quality metrics: ROC AUC, Brier score, expected calibration error, precision@10%, reliability bins and per-fold results.
- Walk-forward backtesting endpoint (`/v1/models/risk/backtest`) with weighted fold summaries.
- Model registry and `/intelligence/quality` admin page.
- Batch risk endpoint (`/v1/predict/risk/batch`) powering task-board and issue-list risk badges.

### Added — prescriptive intelligence

- Monte Carlo sprint forecasting with dependency ordering, per-assignee queues, capacity, historical cycle-time sampling, fixed seed and explicit assumptions.
- Forecast risk drivers showing which tasks finish last most often.
- What-if scenarios for extra days and capacity changes.
- Assignee recommendations for issues, sprints and draft tasks using on-time history, current load, tag overlap and capacity fit.
- CP-SAT sprint optimizer with one owner per task, per-person capacity, WIP limits and a fairness cap; deterministic greedy fallback.
- Baseline vs optimizer comparison: expected fit, lift, changed owners, per-user projected hours and utilization.
- Apply reviewed assignments with manager/admin permission, issue-history logging and `assignment_run`/`assignment_item` audit rows.

### Added — command center, timeline and assistant

- Project command center (`/intelligence/health`) combining sprint confidence, risk distribution, top risks, workload, model health, engineering activity and recent activity.
- Sprint timeline / Gantt (`/intelligence/timeline/@id`) with risk-colored bars, owners, hours, dependency counts, weekly ticks, today marker and legend.
- Grounded project assistant (`/intelligence/ask`) for sprint summaries, forecasts, risk, workload, assignment and duplicate questions, with citations and deterministic answers.
- Print / PDF styling for the command center.

### Added — collaboration and search

- In-app notification center with per-user notifications for issue updates and comments, unread badge, polling, per-item read and mark-all-read.
- Notification generation targeting watchers, owners and authors, excluding the actor.
- TF-IDF duplicate detection over issue titles and descriptions.
- Similar-issues panel on every issue page and a draft duplicate warning on the new/edit issue form.
- Risk badges on task-board cards and issue-list rows.

### Added — GitHub integration

- Signed GitHub webhook receiver at `/webhooks/github` with `X-Hub-Signature-256` verification.
- Commit and pull-request linking via `#123` references in PR titles, bodies, branches and commit messages.
- DORA-ready events in `dora_event`, including PR cycle-time metadata.
- Linked work on the issue page and engineering activity on the command center.
- Optional auto-close of linked issues on PR merge (`github.auto_close`).
- Admin Integrations tab for ML and GitHub settings.
- Setup guide and local webhook simulation in `docs/github-integration.md`.

### Added — security, compatibility and data

- New tables: `model_run`, `prediction`, `suggestion_log`, `forecast_run`, `assignment_run`, `assignment_item`, `user_skill`, `user_availability`, `holiday`, `git_installation`, `issue_link`, `dora_event`, `audit_log`, `job`, `event_outbox` and `notification`.
- `issue.version` and additional query indexes.
- Widened `user.password`/`user.salt` for modern bcrypt hashes.
- CSRF protection on new write routes, issue-level access checks, manager/admin guards and access-filtered similarity results.
- Signed webhook verification and secret configuration.
- PHP 8.5.12 runtime (latest security release) and `Pdo\Mysql::ATTR_INIT_COMMAND`.
- `league/commonmark` updated to 2.10.4; `composer audit --locked` reports no vulnerabilities.
- Config persisted in a dedicated volume so container recreation cannot wipe the database.
- Notification template rendering hardened for installations without IMAP configuration.

### Added — demo, docs and tests

- Deterministic demo generator: 5 users, 3 projects, 14 sprints, 360 closed tasks, current-sprint work, tags, dependencies and issue history.
- `cron/migrate.php`, `cron/refresh_ml.php` and Makefile targets.
- `docs/intelligence-layer.md`, `docs/github-integration.md`, project README and UI screenshots.
- 27 Python tests covering health, auth, risk, batch risk, cycle time, forecasting, what-if, assignment, optimizer, backtesting, similarity search and the assistant.
- 24 PHP tests (2 skipped), with PHPCS, PHPStan and Ruff passing on PHP 8.5.12.

### Fixed

- Admin task board now defaults to **all tasks** instead of an empty “my groups” view.
- Command center, timeline and model-quality pages now include footer scripts, so the assistant and notification polling initialize.
- PHP 8.5 PDO MySQL deprecation removed.
- Container recreation no longer reruns the installer and wipes the database.
- Notification emails no longer break on installations without IMAP settings.

### Security

- PHP 8.5.12 security release pinned.
- Composer audit clean.
- Signed GitHub webhooks.
- CSRF-protected writes.
- Manager/admin authorization on sensitive intelligence views.
- Issue-level access filtering for predictions and similarity results.

### Not yet implemented

- Real-time collaborative task board over SSE/WebSocket.
- Embedding-based semantic search (current duplicate detection is TF-IDF).
- LLM-backed copilot (current assistant is grounded and deterministic).
- Full GitHub App installation flow and a complete DORA dashboard.
- Multi-tenant workspaces, SSO and SCIM.
- GitLab support and an audit-log UI.

See [ROADMAP.md](ROADMAP.md) for the six-month plan and [FEATURE_BACKLOG.md](FEATURE_BACKLOG.md) for all **89** scoped feature additions, execution order and dependencies.

---

**Added by Vedant Chalke.**
