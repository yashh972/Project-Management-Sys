# Employee performance analytics (ML)

`run_analytics.py` reads the task history from the Phproject database, learns what is *expected*
for each task, and judges every employee against that expectation. Results are written back to
three tables that the admin dashboard (`/analytics`) reads. There is no always-on service: it is a
batch job you run on demand, from the dashboard button, or on a schedule.

## Run it

```powershell
# one-time setup (from the project root)
python -m venv ml\.venv
ml\.venv\Scripts\pip install -r ml\requirements.txt

# recompute insights (also available as "Recompute insights" on /analytics)
ml\.venv\Scripts\python ml\run_analytics.py
```

Options: `--db PATH` (default: read from `config.php`), `--now 2026-09-30T04:30` (reproducible runs), `--quiet`.
Currently supports SQLite (`db.engine = sqlite`). All timestamps are UTC, like the app.

Schedule nightly with Windows Task Scheduler or cron: `python ml/run_analytics.py --quiet`.

## Why not just "on-time %"?

Raw counts punish people who are handed harder work and reward people who take easy tasks.
So the pipeline separates *task difficulty* from *person*:

| Step | Model | Sees the assignee? | Purpose |
|---|---|---|---|
| 1. Difficulty: P(late) | Logistic regression / gradient boosting (best on time-split test) | **No** | Expected lateness of a task from its attributes only |
| 2. Difficulty: cycle time | Ridge / gradient boosting on log(days) | **No** | Expected days from activation to completion |
| 3. Late-risk for open tasks | Logistic regression / gradient boosting | Yes: trailing on-time record + open load, both known at task start | "Likely to slip" list |
| 4. Employee score | z-scores + fixed weights | – | 0-100 composite |
| 5. Grouping | KMeans, k=3..4 chosen by silhouette | – | Behaviour groups, named by rule |

Steps 1-2 use out-of-fold predictions, so a task's expectation is never produced by a model that
trained on that same task.

### Features (all engineered from `issue` + the audit trail `issue_update` / `issue_update_field`)

`planned_hours`, `priority`, `is_bug`, `window_days` (time allowed = due date - activation), `queue_days`
(created -> activated), `pressure` (planned hours / window), `act_dow`. The risk model adds
`owner_hist_late` (shrunk late-rate over the assignee's previous 15 closed tasks) and `owner_load`.
Activation = first status change away from *New*; a reopen = any transition out of a closed status.

### Per-employee metrics and score

| Component | Definition | Weight |
|---|---|---|
| Reliability | actual on-time rate - expected on-time rate (mean of 1 - P(late)), shrunk | 35% |
| Speed | geometric mean of expected / actual cycle time, shrunk | 25% |
| Quality | -(reopen rate), shrunk toward the team rate | 15% |
| Estimation | 1 - median abs(hours spent - planned) / planned | 10% |
| Volume | planned hours delivered in the last 12 weeks | 15% |

Small samples are shrunk toward the team mean with prior strength `k = 10` tasks, so someone with 3
tasks cannot top the table. People with fewer than 8 closed tasks are not scored. Each component is
z-scored across the team and mapped to `50 + 15z`, clipped to 2..99. Admin accounts are excluded.
The weights are a judgement call; they are constants at the top of the script and stated on the dashboard.

## Smart assignment model (`assign_model.py`)

Suggests who should take a **new** task. Shown as "Suggest assignee" on the issue form (`GET /assign/suggest`).

```powershell
ml\.venv\Scripts\python mlssign_model.py train      # also runs from "Recompute insights" on /analytics
ml\.venv\Scripts\python mlssign_model.py suggest --type 1 --hours 8 --due 2026-10-09 --tags backend,api
```

For every closed task the script rebuilds what was known about its assignee *at the moment the task started*
(experience, trailing late-rate, speed, open load, record on tasks sharing a tag, tasks of the same type) and
learns two things from that: P(late) (logistic regression vs gradient boosting, best AUC on a time split) and
expected days to finish (ridge vs gradient boosting, best MAE). The model is saved to `ml/assign_model.joblib`
(git-ignored) and metrics go to the `assign_model_run` table.

A candidate's score is `100 * (0.6 * (1 - P(late)) + 0.4 * spare capacity)` with a 40h capacity, minus 15 when the
person has fewer than 3 closed tasks (shown as "limited history"). Only users with role `user` are candidates.

Demo data result: late-model AUC 0.68 (0.5 = guessing), cycle-time MAE 2.4 days vs 3.1 for a "median" guess.

Limitations: it only ranks people, a human still decides; tags are sparse in the demo data so "similar work"
often has no evidence; capacity is a flat 40h; no leave/availability data; retrain after big changes.

## Output tables

| Table | Content |
|---|---|
| `employee_performance` | one row per employee: score, rank, naive rank, cluster, all metrics, strengths/concerns text, radar components |
| `task_risk` | P(late) for every open task |
| `ml_run` | JSON of model-quality metrics for each run |

## Example result (synthetic demo data, 658 closed tasks, time-based 75/25 split)

| Model | Result | Baseline |
|---|---|---|
| Task-difficulty P(late) | AUC 0.52 | 0.50 |
| Late-risk (with assignee history) | AUC 0.66 (logistic regression) | 0.50 |
| Cycle time | MAE 2.4 days (ridge) | 3.1 days (median) |
| Clustering | k = 3, silhouette ~0.24 | – |
| Ranking vs raw on-time % | Spearman ~0.76 | 1.0 = identical |

## Honest limitations (put these in the report)

* **The demo data is synthetic.** Each employee was given a behaviour profile (lateness, speed,
  estimate bias, rework, trend) and tasks were sampled from it. Results show the pipeline recovers
  those patterns; they are **not** evidence about real teams. Validate on real data (for example a
  public Jira dataset) before claiming accuracy.
* **Difficulty barely predicts lateness in this data** (AUC ~0.52), so the fairness adjustment is small
  here. On real data, task attributes usually carry more signal.
* The late-risk AUC (0.66) is modest. Treat the "Likely to slip" list as a prioritisation aid, not a verdict.
* KMeans on ~11 people is unstable (silhouette ~0.24): the clusters are descriptive labels, not classes.
* Composite weights are subjective; run a sensitivity analysis (vary the weights, check rank stability).
* Correlation, not causation: a low score can reflect blockers or unrealistic deadlines, not the person.

## Ethics

Ranking individuals can be misused for surveillance or unfair appraisals. The dashboard is admin-only,
shows *why* a score was given (strengths and concerns), and ranks against task difficulty rather than
raw counts. Recommend using it to spot people who need support and workload imbalance, not as the sole
input for performance reviews.
