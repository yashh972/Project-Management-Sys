#!/usr/bin/env python
"""
Smart assignment model for Phproject.

Given a NEW task (type, planned hours, priority, due date, tags) it ranks the team by who is most likely to
finish it on time, taking current workload and each person's record on similar work into account.

    python assign_model.py train                      fit the models on the task history, save ml/assign_model.joblib
    python assign_model.py suggest --type 1 --hours 6 --priority 0 --due 2026-10-10 --tags backend,api

How it works (see ml/README.md)
-------------------------------
Training data: every closed task with its real assignee. For each one we rebuild what was known about
that assignee at the moment the task started - never using anything from the future:

    experience        closed tasks before this one
    recent late rate  trailing late-rate (last 15 tasks, shrunk toward the team rate)
    speed             trailing days-per-planned-hour (shrunk toward the team)
    load              open tasks / open hours they already had
    similar work      how many earlier tasks shared a tag with this one, and their late rate on those
    same type         earlier tasks of the same type (task / bug)

plus the task itself (planned hours, priority, bug?, days allowed, number of tags, hours per day allowed).

Two models are fitted and validated on a time split (train on the past, test on the newest 25%):
    late model    P(task finishes after its due date)        logistic regression vs gradient boosting, best AUC wins
    cycle model   expected days from start to done            ridge vs gradient boosting, best MAE wins

Suggestion = for each candidate, build the same features "as of now", predict P(late) and cycle days, then
    score = 100 * (0.6 * (1 - P(late)) + 0.4 * spare capacity)       capacity = 40h per person
so a person with a great record but a full plate does not automatically win, and an idle person with no
history on this kind of work is flagged "limited history" instead of being trusted blindly.
"""
import argparse
import json
import sqlite3
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_analytics import find_db, load  # noqa: E402

warnings.filterwarnings("ignore")
MODEL_PATH = Path(__file__).resolve().parent / "assign_model.joblib"

CAPACITY_HOURS = 40.0
W_FIT, W_CAPACITY = 0.6, 0.4
LIMITED_PENALTY = 15
SHRINK = 5
WINDOW = 15
FEATURES = [
    "planned_hours", "priority", "is_bug", "window_days", "n_tags", "pressure",
    "o_exp", "o_late_rate", "o_speed", "o_load_tasks", "o_load_hours", "o_sim_n", "o_sim_late", "o_type_n",
]


# ----------------------------------------------------------------------------- data
def load_tags(con):
    tags = {}
    for issue_id, tag in con.execute("select issue_id, tag from issue_tag"):
        tags.setdefault(int(issue_id), set()).add(str(tag).lower())
    return tags


def prepare_done(issues, tags):
    done = issues[(issues["status_closed"] == 1) & issues["closed_date"].notna() & issues["owner_id"].notna()
                  & issues["due_date"].notna() & issues["activated"].notna()].copy()
    median_h = float(done["hours_total"].replace(0, np.nan).median() or 4.0)
    done["planned"] = done["hours_total"].replace(0, np.nan).fillna(median_h)
    due_end = done["due_date"] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    done["late"] = (done["closed_date"] > due_end).astype(int)
    done["cycle_days"] = ((done["closed_date"] - done["activated"]).dt.total_seconds() / 86400).clip(lower=0.05)
    done["window"] = ((done["due_date"] + pd.Timedelta(days=1) - done["activated"]).dt.total_seconds() / 86400).clip(lower=0.5)
    done["tags"] = done["id"].map(lambda i: tags.get(int(i), set()))
    done["speed"] = done["cycle_days"] / done["planned"].clip(lower=0.5)
    return done.sort_values("activated").reset_index(drop=True), median_h


def owner_state(done, owner, before, task_tags, task_type, team_rate, team_speed, load_tasks, load_hours):
    """Everything known about `owner` strictly before `before`."""
    prev = done[(done["owner_id"] == owner) & (done["closed_date"] < before)].sort_values("closed_date")
    recent = prev.tail(WINDOW)
    n = len(recent)
    late_rate = (recent["late"].sum() + team_rate * SHRINK) / (n + SHRINK)
    speed = (recent["speed"].sum() + team_speed * SHRINK) / (n + SHRINK)
    mask = [bool(t & task_tags) for t in prev["tags"]] if task_tags else [False] * len(prev)
    sim = prev[np.array(mask, dtype=bool)]
    sim_n = len(sim)
    sim_late = (sim["late"].sum() + late_rate * 3) / (sim_n + 3)
    return {
        "o_exp": float(len(prev)), "o_late_rate": float(late_rate), "o_speed": float(speed),
        "o_load_tasks": float(load_tasks), "o_load_hours": float(load_hours),
        "o_sim_n": float(sim_n), "o_sim_late": float(sim_late), "o_type_n": float((prev["type_id"] == task_type).sum()),
    }


def task_part(planned, priority, is_bug, window, n_tags):
    return {
        "planned_hours": float(planned), "priority": float(priority), "is_bug": float(is_bug),
        "window_days": float(window), "n_tags": float(n_tags), "pressure": float(planned) / max(float(window), 0.5),
    }


def training_frame(done):
    team_rate = float(done["late"].mean())
    team_speed = float(done["speed"].median())
    rows = []
    for _, t in done.iterrows():
        start = t["activated"]
        # what the assignee was already carrying when this task started
        mine = done[(done["owner_id"] == t["owner_id"]) & (done["id"] != t["id"]) & (done["activated"] < start) & (done["closed_date"] > start)]
        row = task_part(t["planned"], t["priority"], t["type_id"] == 3, t["window"], len(t["tags"]))
        row.update(owner_state(done, t["owner_id"], start, t["tags"], t["type_id"], team_rate, team_speed, len(mine), mine["planned"].sum()))
        rows.append(row)
    return pd.DataFrame(rows)[FEATURES], team_rate, team_speed


# ----------------------------------------------------------------------------- train
def train(con, db_path):
    issues, _ = load(con)
    tags = load_tags(con)
    done, median_h = prepare_done(issues, tags)
    if len(done) < 60:
        sys.exit(f"Not enough closed tasks to train ({len(done)} found, need 60+).")
    X, team_rate, team_speed = training_frame(done)
    y = done["late"]
    ylog = np.log(done["cycle_days"])
    cut = int(len(X) * 0.75)
    tr, te = X.index[:cut], X.index[cut:]

    late_c = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5)),
        "gradient_boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0),
    }
    report = {"late_model": {"base_rate_test": float(y.loc[te].mean()), "candidates": {}}, "cycle_model": {"candidates": {}}}
    best_auc, late_name = -1.0, None
    for name, m in late_c.items():
        m.fit(X.loc[tr], y.loc[tr])
        p = m.predict_proba(X.loc[te])[:, 1]
        auc = float(roc_auc_score(y.loc[te], p)) if y.loc[te].nunique() > 1 else 0.5
        report["late_model"]["candidates"][name] = {"auc": round(auc, 3), "brier": round(float(brier_score_loss(y.loc[te], p)), 4)}
        if auc > best_auc:
            best_auc, late_name = auc, name
    report["late_model"]["chosen"] = late_name

    cyc_c = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
        "gradient_boosting": HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0),
    }
    base_mae = float(mean_absolute_error(np.exp(ylog.loc[te]), np.full(len(te), np.exp(ylog.loc[tr].median()))))
    report["cycle_model"]["candidates"]["baseline_median"] = {"mae_days": round(base_mae, 2)}
    best_mae, cyc_name = 1e9, None
    for name, m in cyc_c.items():
        m.fit(X.loc[tr], ylog.loc[tr])
        mae = float(mean_absolute_error(np.exp(ylog.loc[te]), np.exp(m.predict(X.loc[te]))))
        report["cycle_model"]["candidates"][name] = {"mae_days": round(mae, 2)}
        if mae < best_mae:
            best_mae, cyc_name = mae, name
    report["cycle_model"]["chosen"] = cyc_name

    # refit the chosen models on all history
    late = late_c[late_name].fit(X, y)
    cycle = cyc_c[cyc_name].fit(X, ylog)
    now = pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    report.update({"n_tasks": int(len(done)), "n_train": int(len(tr)), "n_test": int(len(te)), "trained_at": now.strftime("%Y-%m-%d %H:%M:%S")})
    joblib.dump({"late": late, "cycle": cycle, "team_rate": team_rate, "team_speed": team_speed, "median_hours": median_h, "report": report}, MODEL_PATH)

    con.execute("create table if not exists assign_model_run (id integer primary key autoincrement, trained_at text not null, metrics text not null)")
    con.execute("insert into assign_model_run (trained_at, metrics) values (?, ?)", (report["trained_at"], json.dumps(report)))
    con.commit()
    return report


# ----------------------------------------------------------------------------- suggest
def suggest(con, args):
    if not MODEL_PATH.exists():
        train(con, None)
    bundle = joblib.load(MODEL_PATH)
    issues, users = load(con)
    tags = load_tags(con)
    done, _ = prepare_done(issues, tags)
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    task_tags = {t.strip().lower().lstrip("#") for t in (args.tags or "").split(",") if t.strip()}
    hours = float(args.hours) if args.hours else bundle["median_hours"]
    if args.due:
        window = max(0.5, (pd.Timestamp(args.due) + pd.Timedelta(days=1) - now).total_seconds() / 86400)
    else:
        window = 7.0
    exclude = {int(x) for x in (args.exclude or "").split(",") if x.strip().isdigit()}

    open_ = issues[(issues["status_closed"] == 0) & issues["owner_id"].notna()]
    open_hours = open_["hours_remaining"].where(open_["hours_remaining"] > 0, open_["hours_total"]).fillna(bundle["median_hours"])
    open_ = open_.assign(eff_hours=open_hours)

    out = []
    for _, u in users[(users["role"] == "user")].iterrows():
        uid = int(u["id"])
        if uid in exclude:
            continue
        mine = open_[open_["owner_id"] == uid]
        row = task_part(hours, args.priority, args.type == 3, window, len(task_tags))
        row.update(owner_state(done, uid, now, task_tags, args.type, bundle["team_rate"], bundle["team_speed"], len(mine), mine["eff_hours"].sum()))
        X = pd.DataFrame([row])[FEATURES]
        p_late = float(bundle["late"].predict_proba(X)[:, 1][0])
        days = float(np.exp(bundle["cycle"].predict(X)[0]))
        load_h = float(mine["eff_hours"].sum())
        spare = float(np.clip(1 - (load_h + hours) / CAPACITY_HOURS, 0, 1))
        score = round(100 * (W_FIT * (1 - p_late) + W_CAPACITY * spare))
        limited = row["o_exp"] < 3
        if limited:
            score = max(0, score - LIMITED_PENALTY)  # unproven: do not let an empty history look like a strong record
        reasons = [f"{len(mine)} open task{'s' if len(mine) != 1 else ''}, {load_h:.0f}h queued"]
        if row["o_sim_n"] >= 2:
            reasons.append(f"{(1 - row['o_sim_late']) * 100:.0f}% on time across {int(row['o_sim_n'])} similar tasks")
        elif task_tags:
            reasons.append("no similar tasks done yet")
        if row["o_exp"] >= 3:
            reasons.append(f"{(1 - row['o_late_rate']) * 100:.0f}% on time recently ({int(min(row['o_exp'], WINDOW))} tasks)")
        if limited:
            reasons.append("limited history, treat as a guess")
        if load_h + hours > CAPACITY_HOURS:
            reasons.append(f"over {CAPACITY_HOURS:.0f}h capacity with this task")
        out.append({
            "user_id": uid, "name": u["name"], "score": int(score), "p_late": round(p_late * 100), "expected_days": round(days, 1),
            "open_tasks": int(len(mine)), "open_hours": round(load_h, 1), "limited_history": bool(limited), "reasons": reasons,
        })
    out.sort(key=lambda r: (-r["score"], r["p_late"], r["open_hours"]))
    rep = bundle["report"]
    chosen = rep["late_model"]["chosen"]
    return {
        "suggestions": out[: args.top],
        "model": {"trained_at": rep["trained_at"], "late_model": chosen.replace("_", " "), "auc": rep["late_model"]["candidates"][chosen]["auc"], "tasks": rep["n_tasks"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["train", "suggest"])
    ap.add_argument("--db")
    ap.add_argument("--now")
    ap.add_argument("--type", type=int, default=1)
    ap.add_argument("--hours", type=float)
    ap.add_argument("--priority", type=float, default=0)
    ap.add_argument("--due")
    ap.add_argument("--tags")
    ap.add_argument("--exclude")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    db = find_db(args.db)
    if not db.exists():
        sys.exit(f"Database not found: {db}")
    con = sqlite3.connect(db)
    try:
        if args.command == "train":
            rep = train(con, db)
            if not args.quiet:
                print(json.dumps(rep, indent=2))
        else:
            print(json.dumps(suggest(con, args)))
    finally:
        con.close()


if __name__ == "__main__":
    main()
