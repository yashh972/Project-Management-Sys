[![CI](https://github.com/Alanaktion/phproject/workflows/CI/badge.svg)](https://github.com/Alanaktion/phproject/actions?query=workflow%3ACI)
[![Crowdin](https://badges.crowdin.net/phproject/localized.svg)](https://crowdin.com/project/phproject)

# Phproject

*A high-performance project management system in PHP*

## Installation

Download and extract [the latest release](https://github.com/Alanaktion/phproject/releases/latest) a web accessible directory, go to the page in a browser, and fill in your database connection details.

Detailed requirements and installation instructions are available at [phproject.org](http://www.phproject.org/install.html).

## Project intelligence layer

This fork adds a Python/FastAPI sidecar with task late-risk prediction, sprint
delivery forecasting, assignee recommendations, model quality metrics and an
analytics bridge. The PHP application calls it over HTTP; it never shells out.

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app php cron/seed_demo.php
# http://localhost:9090 — demo_alice / demo1234
```

See [docs/intelligence-layer.md](docs/intelligence-layer.md) for endpoints,
architecture, migrations and development commands.

## Development

Phproject uses [Composer](https://getcomposer.org/) for dependency management. After cloning the repository, run `composer install` to install the required packages.

## Contributing

Phproject is maintained as an open source project for use by anyone around the world under the [GNU General Public License](http://www.gnu.org/licenses/gpl-3.0.txt). If you find a bug or would like a new feature added, [open an issue](https://github.com/Alanaktion/phproject/issues/new) or [submit a pull request](https://github.com/Alanaktion/phproject/compare/) with new code. If you want to help with translation, [you can submit translations via Crowdin](https://crowdin.com/project/phproject).

---

## Changelog

### Project Intelligence Layer — Added by Vedant Chalke

This fork turns Phproject into **Agile CodeBoard**, a project-management platform with a predictive, prescriptive and explainable intelligence layer. PHP remains the system of record and owns authentication, access control and workflow. A Python/FastAPI sidecar owns models, forecasting and optimization; the PHP application calls it over HTTP and never shells out to Python.

#### Predictive intelligence

- **Calibrated task late-risk model** — logistic regression trained on the audit-backed task history (`issue`, `issue_update`, `issue_update_field`, `issue_tag`), with expanding-window validation and sigmoid calibration.
- **Time-aware features** — planned hours, priority, bug flag, allowed window, queue time, pressure, activation day, owner trailing late rate (shrunk toward the team rate) and owner load. Features are computed only from information available when a task starts.
- **Model quality metrics** — ROC AUC, Brier score, expected calibration error (ECE), precision at the top 10%, reliability-curve data and per-fold results.
- **Walk-forward backtesting** — trains on the past and tests on the next time block; reports per-fold and weighted aggregate metrics instead of a random split.
- **Cycle-time estimates** — empirical P50/P85/P95 from activation-to-close history, used by forecasts and the issue form.
- **Model registry** — every trained risk model is recorded in `model_run` with version, row count, metrics, dataset hash and active flag.
- **Per-issue explanations** — the top contributing features and direction for every risk prediction.

#### Prescriptive intelligence

- **Monte Carlo sprint forecasting** — samples historical cycle times, respects `issue_dependency` ordering, queues work per assignee, applies capacity and returns the probability of finishing on time plus P50/P85/P95 dates.
- **Risk drivers** — shows which tasks are most often the last to finish across simulations, with criticality scores and median finish dates.
- **Reproducible forecasts** — fixed seed and explicit assumptions (simulation count, historical samples, dependency handling, capacity, data source) returned with every forecast.
- **What-if scenarios** — re-run a forecast with extra days, reduced or increased capacity, or both, directly from the forecast modal; the scenario is echoed back in the assumptions.
- **Assignee recommendations** — ranks the team for an existing issue, an entire sprint or a draft task using trailing on-time rate, current open hours, tag overlap, historical sample size and capacity fit.
- **Prescriptive sprint optimizer** — OR-Tools CP-SAT assignment with one owner per task, per-person capacity, WIP limits and a configurable fairness cap; falls back to a deterministic greedy solver when CP-SAT is unavailable.
- **Baseline and lift** — compares the optimizer's expected fit against the current assignment, reports changed owners, projected hours, utilization per person and the fairness cap used.
- **Apply reviewed assignments** — managers and admins can apply the optimizer's changes in one action; every change uses `Model\Issue::save()`, so the normal issue history and audit trail still fire, and each applied run is recorded in `assignment_run`/`assignment_item`.
- **Optimizer preview UI** — a sprint-board modal shows the solver, fit/lift, fairness state, per-user load, every proposed owner change and an apply-all action for managers.

#### Feedback, trust and evaluation

- **Suggestion feedback loop** — `suggestion_log` records shown, accepted, rejected, overridden and ignored suggestions with the model payload and acting user, so acceptance and realized lift can be measured later.
- **Model quality page** — an admin view with AUC, Brier, ECE, precision@10%, walk-forward folds, reliability bins and active model versions.
- **Explainable risk chip** — open issues show a calibrated late-risk percentage on hover, with the top contributing factors and model version.
- **Admin-only access** — model quality and model registry routes require an administrator; issue-level endpoints enforce `allowAccess()`.

#### Application integration

- **HTTP ML client** — `Helper\Ml` replaces the previous `exec()` calls with a timeout-aware HTTP client, internal token authentication, error handling and graceful fallback.
- **JSON intelligence endpoints** — `/intelligence/risk/@id`, `/intelligence/cycle/@id`, `/intelligence/forecast/@sprint`, `/intelligence/optimize`, `/intelligence/models`, `/intelligence/quality` and `/intelligence/suggestions/log`.
- **Sprint forecast modal** — probability on time, P50/P85/P95 dates, biggest drivers and assumptions, available from the task board.
- **Optimized assignment modal** — solver, expected fit, baseline fit, lift, fairness cap, owner changes and per-user utilization.
- **Risk chip on issue pages** — no page reload; the chip fetches the prediction and renders a color-coded risk level.
- **Batch risk badges** — task-board cards load calibrated risk percentages in one request, with a low/medium/high color code.
- **Suggestion impressions** — every ranked assignee list logs a `shown` event before an acceptance is recorded, enabling a real acceptance funnel.
- **Analytics integration** — the existing “Recompute insights” action now calls the ML service; the legacy analytics scripts remain available through a compatibility bridge.
- **MySQL analytics bridge** — mirrors the tables the legacy scripts need into a temporary SQLite database, runs the scripts, and syncs the result tables back to MySQL. SQLite remains the native path.
- **CSRF-protected feedback logging** — assignment acceptances are logged through the existing CSRF mechanism.
- **Access checks** — issue suggestions and predictions verify issue visibility; model administration verifies the admin role.

#### Data, migrations and deployment

- **New schema** — `model_run`, `prediction`, `suggestion_log`, `forecast_run`, `assignment_run`, `assignment_item`, `user_skill`, `user_availability`, `holiday`, `git_installation`, `issue_link`, `dora_event`, `audit_log`, `job` and `event_outbox`, plus `issue.version` for future optimistic locking and query indexes.
- **Dual-dialect migrations** — separate MySQL (`26.10.28.sql`, `26.10.29.sql`) and SQLite (`26.10.28.sqlite.sql`, `26.10.29.sqlite.sql`) files, with engine-aware migration selection.
- **Password-width migration** — widens `user.password` and `user.salt` so modern bcrypt hashes fit.
- **Config persistence** — a dedicated `app_config` volume plus a config symlink prevents container recreation from wiping the database.
- **One-command stack** — `docker-compose.yml` with app, MySQL, ML service, Redis, Mercure, Qdrant, MailHog and dev tooling profiles; application and ML health checks.
- **Multi-stage images** — Composer dependency stage, PHP production image with the required extensions, dev image with test dependencies, and a separate Python production/dev image.
- **Makefile and environment template** — `make up`, `down`, `migrate`, `seed`, `test`, `lint`, `train`, `forecast` and `backup`; `.env.example` documents every setting.
- **CI** — PHP matrix (MySQL/SQLite), Python lint and pytest job, and Docker build verification.

#### Demo, documentation and tests

- **Deterministic demo data** — 5 users, 3 projects, 14 sprints, 360 closed tasks with realistic lateness profiles, open sprint work, tags, dependencies and activation history; demo login `demo_alice / demo1234`.
- **Documentation** — `docs/intelligence-layer.md` covers architecture, endpoints, migrations, model notes and limitations; this README links to it.
- **Automated tests** — 18 Python tests covering health, authentication, risk, batch risk, cycle time, forecasting, what-if scenarios, assignment, optimizer, backtesting and feedback; 24 PHP tests (2 skipped), PHPCS, PHPStan and Ruff all green locally.
- **Operational scripts** — `cron/migrate.php`, `cron/refresh_ml.php` and `cron/seed_demo.php`.

#### Not yet implemented (reserved for later phases)

The schema reserves tables for GitHub/GitLab integration, DORA metrics, audit logging, background jobs and outbox events, but those features are not wired into the UI yet. Real-time collaboration, semantic search/duplicate detection, the LLM copilot and multi-tenant SSO are planned next. The legacy analytics MySQL bridge is a compatibility layer, not the long-term pipeline.

**Added by Vedant Chalke.**
