#!/usr/bin/env python
"""
Employee performance analytics for Phproject.

Reads issues + the audit trail (issue_update / issue_update_field) from the Phproject
database, and writes three tables that the admin dashboard (/analytics) reads:

    employee_performance  one row per employee: metrics, 0-100 score, rank, cluster, insights
    task_risk             probability that each open task will finish late
    ml_run                model quality metrics of the latest run (shown on the dashboard)

Method (see ml/README.md for the report-ready description)
----------------------------------------------------------
A plain "on-time %" punishes people who are given harder tasks. So we first learn what is
*expected* for a task from its attributes only (planned hours, priority, type, time allowed,
queueing time) WITHOUT knowing who did it:

    1. Late-risk model     P(task finishes after its due date)       (classifier)
    2. Cycle-time model    expected days from activation to closing  (regressor)

Each employee is then judged against those expectations:

    reliability  = actual on-time rate - expected on-time rate        (shrunk)
    speed        = expected cycle time / actual cycle time            (shrunk, log scale)
    quality      = 1 - reopen rate
    estimation   = 1 - median |hours spent - hours planned| / planned
    volume       = planned hours delivered in the last 12 weeks

These are z-scored across the team and combined with fixed weights into a 0-100 score.
KMeans (k chosen by silhouette) then groups people into behaviour clusters.

Usage:   python run_analytics.py [--db PATH] [--now YYYY-MM-DD[THH:MM]] [--quiet]
"""
import argparse
import json
import re
import sqlite3
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, brier_score_loss, mean_absolute_error, r2_score, roc_auc_score, silhouette_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent

FEATURES = ["planned_hours", "priority", "is_bug", "window_days", "queue_days", "pressure", "act_dow"]
WEIGHTS = {"reliability": 0.35, "speed": 0.25, "quality": 0.15, "estimation": 0.10, "volume": 0.15}
MIN_TASKS = 8          # employees with fewer closed tasks get no score
SHRINK_K = 10          # prior strength (in tasks) for shrinking noisy per-person estimates


# ----------------------------------------------------------------------------- loading
def find_db(arg):
    if arg:
        return Path(arg)
    cfg = (ROOT / "config.php").read_text(encoding="utf-8") if (ROOT / "config.php").exists() else ""
    engine = re.search(r"'db\.engine'\s*=>\s*'(\w+)'", cfg)
    if engine and engine.group(1) != "sqlite":
        sys.exit("run_analytics.py currently supports SQLite databases only (db.engine = %s)." % engine.group(1))
    name = re.search(r"'db\.name'\s*=>\s*'([^']+)'", cfg)
    return (ROOT / (name.group(1) if name else "phproject.db"))


def load(con):
    closed_ids = [str(r[0]) for r in con.execute("select id from issue_status where closed = 1")]
    issues = pd.read_sql_query(
        """select i.id, i.type_id, i.status, s.closed as status_closed, i.owner_id, i.parent_id, i.priority,
                  i.hours_total, i.hours_remaining, i.hours_spent, i.created_date, i.closed_date, i.due_date
           from issue i join issue_status s on s.id = i.status
           where i.type_id <> 2 and i.deleted_date is null""", con)
    upd = pd.read_sql_query(
        """select u.issue_id, u.created_date, f.old_value, f.new_value
           from issue_update u join issue_update_field f on f.issue_update_id = u.id
           where f.field = 'status' order by u.created_date""", con)
    users = pd.read_sql_query("select id, username, name, role from user where role <> 'group' and deleted_date is null", con)
    for c in ("created_date", "closed_date"):
        issues[c] = pd.to_datetime(issues[c])
    issues["due_date"] = pd.to_datetime(issues["due_date"])
    upd["created_date"] = pd.to_datetime(upd["created_date"])

    # first time a task left "New" -> activation; closed -> anything else = reopen
    started = upd[~upd["new_value"].isin(closed_ids)].groupby("issue_id")["created_date"].min().rename("activated")
    reopens = upd[upd["old_value"].isin(closed_ids) & ~upd["new_value"].isin(closed_ids)].groupby("issue_id").size().rename("reopens")
    issues = issues.merge(started, left_on="id", right_index=True, how="left").merge(reopens, left_on="id", right_index=True, how="left")
    issues["reopens"] = issues["reopens"].fillna(0)
    return issues, users


def task_features(df, window_end):
    """Features knowable when the task starts. window_end = due date at end of day."""
    out = pd.DataFrame(index=df.index)
    out["planned_hours"] = df["planned"]
    out["priority"] = df["priority"]
    out["is_bug"] = (df["type_id"] == 3).astype(int)
    out["window_days"] = df["window"]
    out["queue_days"] = df["queue"]
    out["pressure"] = out["planned_hours"] / out["window_days"].clip(lower=0.5)
    out["act_dow"] = df["start"].dt.dayofweek
    return out[FEATURES].astype(float)


def owner_history(done, owner_id, before, prior_rate, k=5, window=15):
    """Assignee's trailing late-rate (last `window` tasks closed before `before`, shrunk) and open load then."""
    g = done[done["owner_id"] == owner_id]
    prev = g[g["closed_date"] < before].sort_values("closed_date").tail(window)
    rate = (prev["late"].sum() + prior_rate * k) / (len(prev) + k)
    load = int(((g["activated"] < before) & (g["closed_date"] > before)).sum())
    return float(rate), load


# ----------------------------------------------------------------------------- models
def time_split(df, frac=0.75):
    order = df.sort_values("activated").index
    cut = int(len(order) * frac)
    return order[:cut], order[cut:]


def fit_late_model(X, y, tr, te):
    cands = {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "gradient_boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0),
    }
    report = {"base_rate_test": float(y.loc[te].mean()), "candidates": {}}
    report["candidates"]["baseline_constant"] = {"auc": 0.5, "brier": float(brier_score_loss(y.loc[te], np.full(len(te), y.loc[tr].mean())))}
    best, best_auc = None, -1
    for name, m in cands.items():
        m.fit(X.loc[tr], y.loc[tr])
        p = m.predict_proba(X.loc[te])[:, 1]
        auc = float(roc_auc_score(y.loc[te], p))
        report["candidates"][name] = {"auc": round(auc, 4), "brier": round(float(brier_score_loss(y.loc[te], p)), 4),
                                      "accuracy": round(float(accuracy_score(y.loc[te], p > 0.5)), 4)}
        if auc > best_auc:
            best, best_auc = name, auc
    report["chosen"] = best
    model = cands[best]
    oof = cross_val_predict(model, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    final = cands[best].fit(X, y)
    return final, oof, report


def fit_cycle_model(X, ylog, tr, te, y_days):
    cands = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "gradient_boosting": HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=200, random_state=0),
    }
    med = float(y_days.loc[tr].median())
    report = {"candidates": {"baseline_median": {"mae_days": round(float(mean_absolute_error(y_days.loc[te], np.full(len(te), med))), 3)}}}
    best, best_mae = None, 1e9
    for name, m in cands.items():
        m.fit(X.loc[tr], ylog.loc[tr])
        pred = m.predict(X.loc[te])
        mae = float(mean_absolute_error(y_days.loc[te], np.exp(pred)))
        report["candidates"][name] = {"mae_days": round(mae, 3), "r2_log": round(float(r2_score(ylog.loc[te], pred)), 4)}
        if mae < best_mae:
            best, best_mae = name, mae
    report["chosen"] = best
    oof = cross_val_predict(cands[best], X, ylog, cv=KFold(5, shuffle=True, random_state=0))
    final = cands[best].fit(X, ylog)
    return final, np.exp(oof), report


# ----------------------------------------------------------------------------- employees
def shrink(value, n, prior=0.0, k=SHRINK_K):
    return (value * n + prior * k) / (n + k)


def pct_score(z):
    return float(np.clip(50 + 15 * z, 2, 99))


def build_employee_table(done, open_, users, now):
    team_reopen = done["reopens"].gt(0).mean()
    rows = []
    for uid, g in done.groupby("owner_id"):
        n = len(g)
        late = g["late"]
        on_time = 1 - late.mean()
        expected = 1 - g["p_late"].mean()
        speed_log = np.log(g["expected_cycle"] / g["cycle_days"]).mean()
        g12 = g[g["closed_date"] >= now - pd.Timedelta(weeks=12)]
        recent = g[g["closed_date"] >= now - pd.Timedelta(days=30)]
        prior = g[(g["closed_date"] < now - pd.Timedelta(days=30)) & (g["closed_date"] >= now - pd.Timedelta(days=90))]
        trend = float((1 - recent["late"].mean()) - (1 - prior["late"].mean())) if len(recent) >= 3 and len(prior) >= 3 else 0.0
        has_hours = g[(g["hours_spent"] > 0) & (g["planned"] > 0)]
        err = ((has_hours["hours_spent"] - has_hours["planned"]).abs() / has_hours["planned"]).median() if len(has_hours) else 0.3
        bias = float((has_hours["hours_spent"] / has_hours["planned"]).mean() - 1) if len(has_hours) else 0.0
        o = open_[open_["owner_id"] == uid]
        hp = g[g["priority"] > 0]
        rows.append(dict(
            user_id=int(uid), tasks_closed=n,
            on_time_rate=float(on_time), expected_on_time=float(expected),
            reliability_raw=float(shrink(on_time - expected, n)),
            speed_index=float(np.exp(shrink(speed_log, n))),
            speed_log=float(shrink(speed_log, n)),
            avg_lateness_days=float(g.loc[late.astype(bool), "lateness_days"].mean()) if late.any() else 0.0,
            reopen_rate=float(shrink(g["reopens"].gt(0).mean(), n, team_reopen)),
            estimate_accuracy=float(np.clip(1 - err, 0, 1)), estimate_bias=bias,
            weekly_throughput=float(len(g12) / 12.0), hours_delivered=float(g12["planned"].sum()),
            trend_delta=trend,
            hp_n=len(hp), hp_late=float(hp["late"].mean()) if len(hp) else np.nan,
            open_tasks=int(len(o)), open_hours=float(o["hours_remaining"].fillna(o["hours_total"]).fillna(0).sum()),
            overdue_open=int((o["due_date"] + pd.Timedelta(days=1) < now).sum()),
        ))
    emp = pd.DataFrame(rows)
    return emp


def phrases(row, z, team_hp_late):
    good, bad = [], []
    if z["reliability"] > 0.4: good.append("Delivers on time even after adjusting for task difficulty")
    if z["reliability"] < -0.4: bad.append("Misses deadlines more often than task difficulty explains")
    if z["speed"] > 0.4: good.append("Finishes tasks faster than expected")
    if z["speed"] < -0.4: bad.append("Takes longer than expected on comparable tasks")
    if z["quality"] > 0.4: good.append("Rarely needs rework - very few reopened tasks")
    if z["quality"] < -0.4: bad.append(f"High rework: {row['reopen_rate']*100:.0f}% of tasks get reopened")
    if z["estimation"] > 0.4: good.append("Accurate hour estimates")
    if z["estimation"] < -0.4:
        b = row["estimate_bias"]
        bad.append(f"Underestimates effort by ~{b*100:.0f}%" if b > 0.1 else "Hour estimates are often off")
    if z["volume"] > 0.4: good.append("Delivers a high volume of work")
    if z["volume"] < -0.4: bad.append("Low delivery volume in the last 12 weeks")
    if row["hp_n"] >= 5 and not np.isnan(row["hp_late"]) and row["hp_late"] - team_hp_late > 0.2:
        bad.append(f"Late on {row['hp_late']*100:.0f}% of high-priority tasks (team: {team_hp_late*100:.0f}%)")
    if row["trend_delta"] > 0.15: good.append(f"Improving: on-time rate +{row['trend_delta']*100:.0f} pts in the last 30 days")
    if row["trend_delta"] < -0.15: bad.append(f"Declining: on-time rate {row['trend_delta']*100:.0f} pts in the last 30 days")
    if row["overdue_open"] >= 2: bad.append(f"{row['overdue_open']} open tasks are already overdue")
    return good[:3], bad[:3]


def label_cluster(c):
    """Rule-based name from a centroid expressed in z-scores."""
    if c["reliability"] > 0.3 and c["speed"] > -0.2: return "Consistent high performer"
    if c["speed"] > 0.3 and c["quality"] < -0.3: return "Fast but error-prone"
    if c["reliability"] < -0.4: return "Needs support"
    if c["volume"] > 0.5: return "High-volume contributor"
    return "Steady contributor"


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--now")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    # the app stores UTC, so "now" must be UTC too (not the machine's local time)
    now = pd.Timestamp(a.now) if a.now else pd.Timestamp(datetime.now(timezone.utc).replace(tzinfo=None))
    db = find_db(a.db)
    if not db.exists():
        sys.exit(f"Database not found: {db}")
    con = sqlite3.connect(db)
    issues, users = load(con)

    # --- closed tasks with a complete lifecycle
    done = issues[(issues["status_closed"] == 1) & issues["closed_date"].notna() & issues["owner_id"].notna()
                  & issues["due_date"].notna() & issues["activated"].notna()].copy()
    if len(done) < 60:
        sys.exit(f"Not enough closed tasks to train models ({len(done)} found, need 60+).")
    done["planned"] = done["hours_total"].fillna(done["hours_total"].median()).replace(0, done["hours_total"].median())
    done["start"] = done["activated"]
    done["window"] = ((done["due_date"] + pd.Timedelta(days=1)) - done["activated"]).dt.total_seconds() / 86400
    done["queue"] = (done["activated"] - done["created_date"]).dt.total_seconds().clip(lower=0) / 86400
    done["cycle_days"] = ((done["closed_date"] - done["activated"]).dt.total_seconds() / 86400).clip(lower=0.05)
    done["late"] = (done["closed_date"].dt.normalize() > done["due_date"].dt.normalize()).astype(int)
    done["lateness_days"] = (done["closed_date"].dt.normalize() - done["due_date"].dt.normalize()).dt.days.clip(lower=0)

    done = done.sort_values("activated").reset_index(drop=True)
    X = task_features(done, None)                 # difficulty features: NO information about who does the work
    prior_late = float(done["late"].mean())
    hist = [owner_history(done, r.owner_id, r.activated, prior_late) for r in done.itertuples()]
    Xr = X.copy()                                 # risk features: + assignee's past record and current load
    Xr["owner_hist_late"] = [h[0] for h in hist]
    Xr["owner_load"] = [h[1] for h in hist]
    tr, te = time_split(done)
    late_model, p_oof, late_report = fit_late_model(X, done["late"], tr, te)
    cyc_model, cyc_oof, cyc_report = fit_cycle_model(X, np.log(done["cycle_days"]), tr, te, done["cycle_days"])
    risk_model, _, risk_report = fit_late_model(Xr, done["late"], tr, te)
    risk_report.update(n_train=len(tr), n_test=len(te), features=list(Xr.columns))
    done["p_late"] = p_oof
    done["expected_cycle"] = cyc_oof
    late_report.update(n_train=len(tr), n_test=len(te), n_total=len(done), late_rate=float(done["late"].mean()))
    cyc_report.update(n_train=len(tr), n_test=len(te))

    # --- open tasks: late risk (remaining work vs remaining time; approximation of the training features)
    op = issues[(issues["status_closed"] == 0) & issues["owner_id"].notna() & issues["due_date"].notna()].copy()
    op["planned"] = op["hours_remaining"].where(op["hours_remaining"] > 0, op["hours_total"]).fillna(done["planned"].median())
    op["start"] = now
    op["window"] = (((op["due_date"] + pd.Timedelta(days=1)) - now).dt.total_seconds() / 86400)
    overdue = op["window"] <= 0
    op["window"] = op["window"].clip(lower=0.05)
    op["queue"] = ((op["activated"].fillna(now) - op["created_date"]).dt.total_seconds().clip(lower=0) / 86400)
    if len(op):
        Xo = task_features(op, None)
        oh = [owner_history(done, r.owner_id, now, prior_late) for r in op.itertuples()]
        Xo["owner_hist_late"] = [h[0] for h in oh]
        Xo["owner_load"] = [int((op["owner_id"] == r.owner_id).sum()) for r in op.itertuples()]
        risk = risk_model.predict_proba(Xo[Xr.columns])[:, 1]
    else:
        risk = np.array([])
    op["p_late"] = np.where(overdue, 1.0, risk)

    # --- employees
    staff = set(users.loc[users["role"] != "admin", "id"])
    emp = build_employee_table(done[done["owner_id"].isin(staff)], op[op["owner_id"].isin(staff)], users, now)
    eligible = emp["tasks_closed"] >= MIN_TASKS
    comp = pd.DataFrame({
        "reliability": emp["reliability_raw"], "speed": emp["speed_log"],
        "quality": -emp["reopen_rate"], "estimation": emp["estimate_accuracy"], "volume": emp["hours_delivered"],
    })
    z = (comp - comp[eligible].mean()) / comp[eligible].std(ddof=0).replace(0, 1)
    z = z.fillna(0)
    emp["score"] = np.where(eligible, [pct_score(sum(WEIGHTS[k] * z.loc[i, k] for k in WEIGHTS)) for i in emp.index], np.nan)
    emp["rank"] = emp["score"].rank(ascending=False, method="min")
    emp["naive_rank"] = emp["on_time_rate"].where(eligible).rank(ascending=False, method="min")

    # --- clustering
    cluster_report = {"k": None}
    emp["cluster"] = "Insufficient data"
    idx = emp.index[eligible]
    if len(idx) >= 6:
        Zs = z.loc[idx].values
        best = None
        for k in range(3, min(5, len(idx) - 1) + 1):
            km = KMeans(n_clusters=k, n_init=25, random_state=0).fit(Zs)
            sil = silhouette_score(Zs, km.labels_)
            if best is None or sil > best[0]:
                best = (sil, k, km)
        sil, k, km = best
        names = {}
        for c in range(k):
            cen = dict(zip(z.columns, km.cluster_centers_[c]))
            names[c] = label_cluster(cen)
        emp.loc[idx, "cluster"] = [names[l] for l in km.labels_]
        cluster_report = {"k": int(k), "silhouette": round(float(sil), 4), "names": {str(c): n for c, n in names.items()}}

    team_hp_late = float(done.loc[done["priority"] > 0, "late"].mean())
    ins_good, ins_bad, comp_json = [], [], []
    for i, row in emp.iterrows():
        g, b = phrases(row, z.loc[i], team_hp_late) if eligible[i] else ([], ["Not enough closed tasks yet for a reliable assessment"])
        ins_good.append(json.dumps(g)); ins_bad.append(json.dumps(b))
        comp_json.append(json.dumps({k: round(pct_score(z.loc[i, k]), 1) for k in WEIGHTS}))
    emp["strengths"], emp["concerns"], emp["components"] = ins_good, ins_bad, comp_json

    rho = float(spearmanr(emp.loc[idx, "rank"], emp.loc[idx, "naive_rank"])[0]) if len(idx) > 2 else None
    metrics = {
        "computed_at": now.strftime("%Y-%m-%d %H:%M:%S"), "n_closed_tasks": len(done), "n_open_tasks": len(op),
        "n_employees_scored": int(eligible.sum()), "late_model": late_report, "risk_model": risk_report, "cycle_model": cyc_report,
        "clustering": cluster_report, "weights": WEIGHTS,
        "rank_correlation_vs_naive_on_time": None if rho is None else round(rho, 3),
        "avg_rank_shift_vs_naive": round(float((emp.loc[idx, "rank"] - emp.loc[idx, "naive_rank"]).abs().mean()), 2) if len(idx) else None,
    }

    # --- persist
    cur = con.cursor()
    cur.executescript("""
        create table if not exists employee_performance (
            user_id integer primary key, score real, rank integer, naive_rank integer, cluster text, tasks_closed integer,
            on_time_rate real, expected_on_time real, reliability real, speed_index real, avg_lateness_days real,
            reopen_rate real, estimate_accuracy real, estimate_bias real, weekly_throughput real, hours_delivered real,
            trend_delta real, open_tasks integer, open_hours real, overdue_open integer,
            strengths text, concerns text, components text, computed_at text);
        create table if not exists task_risk (issue_id integer primary key, p_late real, computed_at text);
        create table if not exists ml_run (id integer primary key autoincrement, computed_at text, metrics text);
        delete from employee_performance; delete from task_risk;""")
    ts = metrics["computed_at"]
    for _, r in emp.iterrows():
        cur.execute("insert into employee_performance values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            r.user_id, None if np.isnan(r.score) else round(float(r.score), 1),
            None if np.isnan(r["rank"]) else int(r["rank"]), None if np.isnan(r.naive_rank) else int(r.naive_rank), r.cluster, int(r.tasks_closed),
            round(r.on_time_rate, 4), round(r.expected_on_time, 4), round(r.reliability_raw, 4), round(r.speed_index, 3), round(r.avg_lateness_days, 2),
            round(r.reopen_rate, 4), round(r.estimate_accuracy, 4), round(r.estimate_bias, 4), round(r.weekly_throughput, 2), round(r.hours_delivered, 1),
            round(r.trend_delta, 4), int(r.open_tasks), round(r.open_hours, 1), int(r.overdue_open), r.strengths, r.concerns, r.components, ts))
    cur.executemany("insert into task_risk values (?,?,?)", [(int(i), round(float(p), 4), ts) for i, p in zip(op["id"], op["p_late"])])
    cur.execute("insert into ml_run (computed_at, metrics) values (?,?)", (ts, json.dumps(metrics)))
    con.commit()

    if not a.quiet:
        names = dict(zip(users["id"], users["name"]))
        print(f"Closed tasks used: {len(done)} | open tasks scored: {len(op)} | employees scored: {int(eligible.sum())}")
        print(f"Difficulty model : chosen={late_report['chosen']}  " + "  ".join(f"{k}: AUC {v['auc']}" for k, v in late_report['candidates'].items()))
        print(f"Risk model       : chosen={risk_report['chosen']}  " + "  ".join(f"{k}: AUC {v['auc']}" for k, v in risk_report['candidates'].items()))
        print(f"Cycle-time model : chosen={cyc_report['chosen']}  " + "  ".join(f"{k}: MAE {v['mae_days']}d" for k, v in cyc_report['candidates'].items()))
        print(f"Clusters         : {cluster_report}")
        print(f"Rank correlation vs naive on-time ranking (Spearman): {metrics['rank_correlation_vs_naive_on_time']}")
        show = emp.sort_values("rank")[["user_id", "score", "rank", "naive_rank", "cluster", "tasks_closed", "on_time_rate", "expected_on_time", "speed_index", "reopen_rate"]]
        print(f"\n{'#':>2} {'Employee':16} {'Score':>5} {'naive#':>6}  {'Cluster':27} {'n':>3} {'on-time':>7} {'expect':>6} {'speed':>5} {'reopen':>6}")
        for _, r in show.iterrows():
            print(f"{'-' if np.isnan(r['rank']) else int(r['rank']):>2} {names.get(int(r.user_id), r.user_id):16} {'-' if np.isnan(r.score) else f'{r.score:5.1f}':>5} "
                  f"{'-' if np.isnan(r.naive_rank) else int(r.naive_rank):>6}  {r.cluster:27} {int(r.tasks_closed):3d} {r.on_time_rate*100:6.0f}% {r.expected_on_time*100:5.0f}% {r.speed_index:5.2f} {r.reopen_rate*100:5.0f}%")
    con.close()


if __name__ == "__main__":
    main()
