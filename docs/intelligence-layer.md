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
| `GET` | `/v1/models` | Active model registry |
| `POST` | `/v1/models/risk/refresh` | Retrain the risk model from current history |
| `POST` | `/v1/train/analytics` | Recompute the legacy analytics/assignment tables |

PHP proxies:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/intelligence/risk/@id` | Issue risk + explanation |
| `GET` | `/intelligence/cycle/@id` | Cycle-time estimate |
| `GET` | `/intelligence/forecast/@sprint` | Sprint forecast |
| `GET` | `/intelligence/models` | Model registry (admin only) |
| `GET` | `/assign/suggest` | Existing assignment widget |
| `POST` | `/analytics/refresh` | Recompute analytics from the UI |

## Data and migrations

`db/26.10.28.sql` (MySQL) and `db/26.10.28.sqlite.sql` add the registry,
prediction, feedback, forecast, assignment, skills/availability, GitHub/DORA,
audit, job and outbox tables, plus `issue.version` for optimistic locking.
`db/26.10.29.*` widens the password column for bcrypt hashes.

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

## Development

```bash
make test-ml      # pytest in the ML dev image
make test-php     # PHPUnit in the app dev image
make lint         # phpcs + phpstan + ruff
make seed         # deterministic demo data
make train        # recompute analytics through the ML service
```
