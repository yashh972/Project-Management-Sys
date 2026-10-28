"""Lightweight similarity search for duplicate detection.

TF-IDF over issue titles and descriptions is intentionally used instead of an
embedding service for the first pass: it is fast, deterministic, has no external
model download, and is good enough to catch duplicate bug reports. The same
interface can later be backed by pgvector/Qdrant embeddings.
"""

from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .features import load_issues


def _clean(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"[#*_`>\[\]()]", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:4000]


def similar_issues(
    issue_id: int | None = None,
    text: str | None = None,
    top_k: int = 5,
) -> dict:
    df = load_issues()
    if df.empty:
        return {"results": [], "corpus": 0}

    documents = (
        df["name"].map(_clean) + " " + df["description"].map(_clean)
    ).tolist()
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=20000,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(documents)

    if issue_id is not None:
        rows = df.index[df["id"] == issue_id].tolist()
        if not rows:
            raise KeyError(f"Issue {issue_id} not found")
        row_index = int(rows[0])
        query = matrix[row_index]
    elif text:
        if not text.strip():
            raise ValueError("Provide an issue id or some text")
        query = vectorizer.transform([_clean(text)])
        row_index = None
    else:
        raise ValueError("Provide an issue id or some text")

    scores = cosine_similarity(query, matrix)[0]
    order = np.argsort(-scores)

    results = []
    for index in order:
        if row_index is not None and int(index) == row_index:
            continue
        score = float(scores[index])
        if score <= 0:
            continue
        row = df.iloc[int(index)]
        results.append(
            {
                "issue_id": int(row["id"]),
                "name": str(row["name"]),
                "score": round(score, 4),
                "status": str(row["status_closed"]),
                "owner": None if "owner_name" not in row or row["owner_name"] is None else str(row["owner_name"]),
            }
        )
        if len(results) >= max(1, min(20, top_k)):
            break

    return {"results": results, "corpus": int(len(df))}
