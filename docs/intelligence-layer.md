# Project intelligence layer

The fork adds a sidecar ML service to Phproject. PHP owns authentication, access
control and the workflow; Python owns models, forecasting and recommendations.
The PHP application never shells out to Python.

## Services

| Service | Port | Purpose |
|---|---|---|
| `app` | `9090` | PHP / Fat-Free application |
| `db` | `3307` on the host | MySQL 8 |
| `ml` | `8000` | FastAPI inference, forecasting and training |
| `redis` | profile `realtime` / `worker` | Queue and pub/sub (reserved) |
| `mercure` | profile `realtime` | SSE hub (reserved) |
| `qdrant` | profile `search` | Vector search (reserved) |
| `mailhog` | profile `dev` | Local email capture |

Quick start:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app php cron/seed_demo.php
open http://localhost:9090
```

Demo accounts created by the seed: `demo_alice / demo1234`, plus
`demo_bob`, `demo_carol`, `demo_dave`. The admin credentials come from
`ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env` (default `admin` /
`change-me-now`).

## API

All inference endpoints require `X-Internal-Token: $ML_INTERNAL_TOKEN`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness and database check |
| `POST` | `/v1/predict/risk` | Calibrated late-risk for one issue |
| `POST` | `/v1/predict/cycle` | Cycle-time estimates (P50/P85) |
| `POST` | `/v1/forecast/sprint` | Monte Carlo sprint forecast |
| `POST` | `/v1/assign/suggest` | Ranked assignees for an issue, sprint or draft task |
| `POST` | `/v1/assign/optimize` | CP-SAT sprint assignment with capacity, WIP and fairness constraints |
| `POST` | `/v1/search/similar` | TF-IDF duplicate / similar-issue search |
| `POST` | `/v1/assistant/ask` | Grounded project assistant (forecast, risk, workload, assignment, duplicates) |
| `GET` | `/v1/models` | Active model registry |
| `POST` | `/v1/models/risk/refresh` | Retrain the risk model from current history |
| `POST` | `/v1/models/risk/backtest` | Walk-forward evaluation + reliability bins |
| `POST` | `/v1/train/analytics` | Recompute the legacy analytics/assignment tables |

PHP proxies:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/intelligence/risk/@id` | Issue risk + explanation |
| `GET` | `/intelligence/cycle/@id` | Cycle-time estimate |
| `GET` | `/intelligence/forecast/@sprint` | Sprint forecast |
| `GET` | `/intelligence/models` | Model registry (admin only) |
| `GET` | `/intelligence/quality` | Model quality page (admin only) |
| `GET` | `/intelligence/health` | Project command center (manager/admin) |
| `GET` | `/intelligence/timeline/@sprint` | Sprint timeline / Gantt view |
| `GET` | `/intelligence/risk-batch?ids=...` | Batch risk for task-board and issue-list badges |
| `GET` | `/intelligence/similar/@id` | Similar issues for an issue |
| `POST` | `/intelligence/similar` | Similar issues for draft text |
| `POST` | `/intelligence/ask` | Grounded assistant |
| `POST` | `/intelligence/optimize` | Optimizer preview |
| `POST` | `/intelligence/optimize/apply` | Apply reviewed assignments (manager/admin) |
| `GET` | `/notifications` | In-app notification center |
| `POST` | `/webhooks/github` | Signed GitHub webhook receiver |
| `GET` | `/assign/suggest` | Existing assignment widget |
| `POST` | `/analytics/refresh` | Recompute analytics from the UI |

## Data and migrations

`db/26.10.28.sql` (MySQL) and `db/26.10.28.sqlite.sql` add the registry,
prediction, feedback, forecast, assignment, skills/availability, GitHub/DORA,
audit, job and outbox tables, plus `issue.version` for optimistic locking.
`db/26.10.29.*` widens the password column for bcrypt hashes.
`db/26.10.30.*` adds the in-app notification table.

Apply migrations with:

```bash
docker compose exec app php cron/migrate.php
```

## Model notes

- The risk model trains on closed tasks, uses a time-ordered 75/25 split, and
  reports AUC/Brier. It is deliberately explainable (logistic regression).
- The sprint forecast samples historical activation-to-close cycle times,
  respects dependencies, and queues work per assignee. It is seeded for
  reproducibility.
- Assignee ranking uses trailing on-time rate, current open hours and tag
  overlap. The OR-Tools optimizer will replace the per-task ranking in the next
  phase.
- The legacy `ml/run_analytics.py` and `ml/assign_model.py` still power the
  analytics dashboard. On MySQL, the service mirrors the required tables into a
  temporary SQLite database, runs the scripts, and syncs the result tables back.
  This is a compatibility bridge, not the long-term pipeline.
- Duplicate detection uses TF-IDF over titles and descriptions. It is fast and
  deterministic; the interface can be replaced by embedding search later.
- The grounded assistant maps questions to project operations and cites the
  issues or sprint it used. It is not a free-form LLM and does not hallucinate
  outside the returned data.
- GitHub webhooks link commits/PRs to issues and store DORA-ready events. See
  [github-integration.md](github-integration.md) for setup and a local payload.

## Development

```bash
make test-ml      # pytest in the ML dev image
make test-php     # PHPUnit in the app dev image
make lint         # phpcs + phpstan + ruff
make seed         # deterministic demo data
make train        # recompute analytics through the ML service
```
