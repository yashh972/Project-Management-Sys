"""Grounded project assistant.

This is deliberately not a free-form chatbot. It maps a question to a small set
of project-intelligence operations (forecast, risk, workload, assignment,
duplicate search) and answers only from the resulting data. That keeps the
answers verifiable and makes an LLM an optional future layer rather than a
source of truth.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pandas as pd

from .assignment import suggest
from .features import load_issues, load_sprints, median_hours
from .forecasting import forecast_sprint
from .risk import risk_service
from .search import similar_issues


def _current_sprint(sprint_id: int | None = None) -> pd.Series | None:
    sprints = load_sprints()
    if sprints.empty:
        return None
    if sprint_id:
        match = sprints[sprints["id"] == sprint_id]
        return None if match.empty else match.iloc[0]

    today = datetime.now(UTC).date().isoformat()
    current = sprints[(sprints["start_date"].astype(str) <= today) & (sprints["end_date"].astype(str) >= today)]
    if not current.empty:
        return current.sort_values("id").iloc[-1]
    return sprints.sort_values("end_date").iloc[-1]


def _open_tasks(sprint_id: int) -> pd.DataFrame:
    df = load_issues()
    return df[
        (df["sprint_id"] == sprint_id)
        & (df["status_closed"] == 0)
        & (df["type_role"] != "project")
    ].copy()


def _citation(issue_id: int, name: str) -> dict:
    return {"label": f"#{issue_id} {name}", "url": f"/issues/{issue_id}"}


def _summary(sprint: pd.Series) -> tuple[str, list[dict]]:
    sprint_id = int(sprint["id"])
    df = load_issues()
    tasks = df[(df["sprint_id"] == sprint_id) & (df["type_role"] != "project")]
    open_tasks = tasks[tasks["status_closed"] == 0]
    closed = int(len(tasks) - len(open_tasks))
    overdue = int(
        (
            open_tasks["due_dt"].notna()
            & (open_tasks["due_dt"] < pd.Timestamp(datetime.now(UTC).date()))
        ).sum()
    )

    risk_counts = {"high": 0, "medium": 0, "low": 0}
    for issue_id in open_tasks["id"].tolist():
        try:
            result = risk_service.predict(int(issue_id))
            risk_counts[result["risk"]] += 1
        except Exception:
            continue

    try:
        forecast = forecast_sprint(sprint_id, 2000)
        chance = round(forecast["probability_on_time"] * 100)
        forecast_text = f" The forecast gives it a {chance}% chance of finishing on time (P85 {forecast['p85_date']})."
    except Exception:
        forecast_text = ""

    answer = (
        f"{sprint['name']} has {len(open_tasks)} open tasks and {closed} completed. "
        f"{overdue} are overdue. Risk: {risk_counts['high']} high, {risk_counts['medium']} medium, "
        f"{risk_counts['low']} low.{forecast_text}"
    )
    citations = [{"label": f"Task board — {sprint['name']}", "url": f"/taskboard/{sprint_id}"}]
    return answer, citations


def _risks(sprint: pd.Series) -> tuple[str, list[dict]]:
    tasks = _open_tasks(int(sprint["id"]))
    scored = []
    for row in tasks.itertuples(index=False):
        try:
            result = risk_service.predict(int(row.id))
            scored.append((result["p_late"], int(row.id), str(row.name), result["risk"]))
        except Exception:
            continue
    scored.sort(reverse=True)
    if not scored:
        return "There are no open tasks with a risk prediction in this sprint.", []
    top = scored[:5]
    listing = "; ".join(f"#{issue_id} {name} ({risk}, {round(p * 100)}%)" for p, issue_id, name, risk in top)
    answer = f"The highest late-risk tasks in {sprint['name']} are: {listing}."
    return answer, [_citation(issue_id, name) for _, issue_id, name, _ in top]


def _workload(sprint: pd.Series) -> tuple[str, list[dict]]:
    df = load_issues()
    open_tasks = df[(df["status_closed"] == 0) & (df["type_role"] != "project")]
    fallback = median_hours(df)
    rows = []
    for owner_id, group in open_tasks.groupby("owner_id", dropna=True):
        hours = group["hours_remaining"].where(group["hours_remaining"] > 0, group["hours_total"])
        hours = float(hours.fillna(fallback).sum())
        name = str(group["owner_name"].dropna().iloc[0]) if group["owner_name"].notna().any() else f"User {int(owner_id)}"
        rows.append((hours, int(owner_id), name, len(group)))
    rows.sort(reverse=True)
    unassigned = int(open_tasks["owner_id"].isna().sum())
    if not rows:
        return "No open work is assigned right now.", []
    top = rows[:5]
    listing = "; ".join(f"{name}: {round(hours)}h across {count} tasks" for hours, _, name, count in top)
    answer = f"Current workload: {listing}."
    if unassigned:
        answer += f" {unassigned} open task(s) are unassigned."
    return answer, [{"label": "Open task board", "url": f"/taskboard/{int(sprint['id'])}"}]


def _assignment(question: str, sprint: pd.Series) -> tuple[str, list[dict]]:
    match = re.search(r"#?(\d{2,})", question)
    if match:
        issue_id = int(match.group(1))
        try:
            result = suggest(issue_id=issue_id, top=3)
        except KeyError:
            return f"I couldn't find issue #{issue_id} in the current data.", []
        candidates = result["recommendations"][0]["candidates"] if result["recommendations"] else []
        if not candidates:
            return f"No assignable candidates were found for #{issue_id}.", []
        listing = "; ".join(
            f"{candidate['name']} (fit {candidate['score']}, {round(candidate['p_on_time'] * 100)}% on-time)"
            for candidate in candidates
        )
        return f"Best matches for #{issue_id}: {listing}.", [_citation(issue_id, f"Issue {issue_id}")]

    try:
        result = suggest(sprint_id=int(sprint["id"]), top=1)
    except KeyError:
        return "There are no open tasks to assign in this sprint.", []
    lines = []
    citations = []
    for recommendation in result["recommendations"][:5]:
        candidate = recommendation["candidates"][0] if recommendation["candidates"] else None
        if candidate:
            lines.append(f"#{recommendation['issue_id']} → {candidate['name']} (fit {candidate['score']})")
            citations.append(_citation(recommendation["issue_id"], recommendation["issue_name"]))
    return "Suggested owners: " + "; ".join(lines) + ".", citations


def _duplicates(question: str) -> tuple[str, list[dict]]:
    match = re.search(r"#?(\d{2,})", question)
    if match:
        issue_id = int(match.group(1))
        try:
            result = similar_issues(issue_id=issue_id, top_k=5)
        except KeyError:
            return f"I couldn't find issue #{issue_id}.", []
    else:
        text = re.sub(
            r"(?i)\b(find|similar|duplicate|duplicates|are there|any|issues?|for|to|the|a|an)\b",
            " ",
            question,
        )
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 5:
            return "Tell me the task title or text, or give me an issue number like #123.", []
        result = similar_issues(text=text, top_k=5)

    results = result["results"]
    if not results:
        return "I didn't find any close matches.", []
    listing = "; ".join(f"#{item['issue_id']} {item['name']} ({round(item['score'] * 100)}%)" for item in results[:5])
    return f"Closest existing issues: {listing}.", [
        _citation(item["issue_id"], item["name"]) for item in results[:5]
    ]


def ask(question: str, sprint_id: int | None = None) -> dict:
    question = question.strip()
    if not question:
        raise ValueError("Ask a question first")

    sprint = _current_sprint(sprint_id)
    if sprint is None:
        return {
            "answer": "There are no sprints yet. Create a sprint to unlock forecasting and risk answers.",
            "citations": [],
            "intent": "empty",
            "generated_at": datetime.now(UTC).isoformat(),
        }

    normalized = question.lower()
    if any(word in normalized for word in ("duplicate", "similar")):
        answer, citations = _duplicates(question)
        intent = "duplicates"
    elif any(word in normalized for word in ("who should", "assign", "owner for", "best person")):
        answer, citations = _assignment(question, sprint)
        intent = "assignment"
    elif any(word in normalized for word in ("overload", "workload", "capacity", "busy", "bandwidth")):
        answer, citations = _workload(sprint)
        intent = "workload"
    elif any(word in normalized for word in ("risk", "risky", "late", "slip")):
        answer, citations = _risks(sprint)
        intent = "risk"
    elif any(word in normalized for word in ("forecast", "on time", "deadline", "finish", "confidence")):
        try:
            forecast = forecast_sprint(int(sprint["id"]), 2000)
        except Exception as exc:
            return {
                "answer": f"The forecast is unavailable: {exc}",
                "citations": [],
                "intent": "forecast",
                "generated_at": datetime.now(UTC).isoformat(),
            }
        chance = round(forecast["probability_on_time"] * 100)
        drivers = ", ".join(f"#{driver['issue_id']} {driver['name']}" for driver in forecast["drivers"][:3])
        answer = (
            f"{sprint['name']} has a {chance}% chance of finishing on time. "
            f"P50 is {forecast['p50_date']} and P85 is {forecast['p85_date']}. "
            + (f"The biggest drivers are {drivers}." if drivers else "")
        )
        citations = [
            {"label": f"Task board — {sprint['name']}", "url": f"/taskboard/{int(sprint['id'])}"}
        ] + [_citation(driver["issue_id"], driver["name"]) for driver in forecast["drivers"][:3]]
        intent = "forecast"
    else:
        answer, citations = _summary(sprint)
        intent = "summary"

    return {
        "answer": answer,
        "citations": citations,
        "intent": intent,
        "sprint_id": int(sprint["id"]),
        "generated_at": datetime.now(UTC).isoformat(),
    }
