"""Request and response contracts for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    database: str
    model: str | None = None
    detail: str | None = None


class ExplanationItem(BaseModel):
    feature: str
    value: float | None = None
    impact: float
    direction: Literal["increases", "decreases"]


class RiskRequest(BaseModel):
    issue_id: int = Field(gt=0)


class RiskResponse(BaseModel):
    issue_id: int
    p_late: float = Field(ge=0, le=1)
    risk: Literal["low", "medium", "high"]
    due_date: str | None = None
    model: str
    model_version: str
    metrics: dict[str, float] | None = None
    explanation: list[ExplanationItem] = Field(default_factory=list)
    generated_at: datetime


class RiskBatchRequest(BaseModel):
    issue_ids: list[int] = Field(min_length=1, max_length=200)


class RiskBatchItem(BaseModel):
    issue_id: int
    p_late: float | None = None
    risk: Literal["low", "medium", "high"] | None = None
    explanation: list[ExplanationItem] = Field(default_factory=list)
    error: str | None = None


class RiskBatchResponse(BaseModel):
    results: list[RiskBatchItem] = Field(default_factory=list)


class SimilarRequest(BaseModel):
    issue_id: int | None = Field(default=None, gt=0)
    text: str | None = Field(default=None, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def has_query(self) -> SimilarRequest:
        if (self.issue_id is None) and not (self.text and self.text.strip()):
            raise ValueError("Provide issue_id or text")
        return self


class SimilarItem(BaseModel):
    issue_id: int
    name: str
    score: float
    status: str
    owner: str | None = None


class SimilarResponse(BaseModel):
    results: list[SimilarItem] = Field(default_factory=list)
    corpus: int = 0


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    sprint_id: int | None = Field(default=None, gt=0)


class AskCitation(BaseModel):
    label: str
    url: str


class AskResponse(BaseModel):
    answer: str
    citations: list[AskCitation] = Field(default_factory=list)
    intent: str
    sprint_id: int | None = None
    generated_at: datetime


class CycleRequest(BaseModel):
    issue_id: int = Field(gt=0)


class CycleResponse(BaseModel):
    issue_id: int
    p50_days: float
    p85_days: float
    expected_days: float
    sample_size: int
    model_version: str
    generated_at: datetime


class ForecastRequest(BaseModel):
    sprint_id: int = Field(gt=0)
    simulations: int = Field(default=5000, ge=200, le=50000)
    capacity_hours_per_day: float = Field(default=8.0, gt=0, le=24)
    extra_days: int = Field(default=0, ge=-30, le=90)
    capacity_multiplier: float = Field(default=1.0, gt=0, le=3)


class ForecastDriver(BaseModel):
    issue_id: int
    name: str
    owner: str | None = None
    median_finish: str
    criticality: float


class ForecastResponse(BaseModel):
    sprint_id: int
    sprint_name: str
    start_date: str
    end_date: str
    open_tasks: int
    probability_on_time: float = Field(ge=0, le=1)
    p50_date: str
    p85_date: str
    p95_date: str
    expected_days: float
    drivers: list[ForecastDriver] = Field(default_factory=list)
    assumptions: dict[str, str | float | int] = Field(default_factory=dict)
    generated_at: datetime


class DraftTask(BaseModel):
    type_id: int = 1
    hours: float | None = Field(default=None, ge=0, le=10000)
    priority: int = 0
    due: str | None = None
    tags: list[str] = Field(default_factory=list)
    exclude: list[int] = Field(default_factory=list)


class AssignRequest(BaseModel):
    issue_id: int | None = Field(default=None, gt=0)
    sprint_id: int | None = Field(default=None, gt=0)
    draft: DraftTask | None = None
    top: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def exactly_one_target(self) -> AssignRequest:
        targets = [self.issue_id is not None, self.sprint_id is not None, self.draft is not None]
        if sum(targets) != 1:
            raise ValueError("Provide exactly one of issue_id, sprint_id or draft")
        return self


class Candidate(BaseModel):
    user_id: int
    name: str
    username: str
    score: float = Field(ge=0, le=100)
    p_on_time: float = Field(ge=0, le=1)
    open_hours: float
    open_tasks: int
    tag_overlap: float = Field(ge=0, le=1)
    limited_history: bool
    reasons: list[str] = Field(default_factory=list)


class TaskRecommendation(BaseModel):
    issue_id: int
    issue_name: str
    candidates: list[Candidate] = Field(default_factory=list)


class AssignResponse(BaseModel):
    issue_id: int | None = None
    sprint_id: int | None = None
    recommendations: list[TaskRecommendation] = Field(default_factory=list)
    generated_at: datetime


class ModelInfo(BaseModel):
    name: str
    version: str
    trained_at: datetime | None = None
    rows: int = 0
    metrics: dict[str, float] = Field(default_factory=dict)
    active: bool = True


class ModelListResponse(BaseModel):
    models: list[ModelInfo] = Field(default_factory=list)


class OptimizeRequest(BaseModel):
    sprint_id: int = Field(gt=0)
    capacity_hours: float | None = Field(default=None, gt=0, le=400)
    max_wip: int = Field(default=5, ge=1, le=50)
    time_limit_seconds: float = Field(default=5.0, ge=0.5, le=30)
    fairness: bool = True


class OptimizeAssignment(BaseModel):
    issue_id: int
    issue_name: str
    user_id: int
    user_name: str
    score: float
    current_owner_id: int | None = None
    changed: bool
    hours: float
    reasons: list[str] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    sprint_id: int
    solver: str
    assignments: list[OptimizeAssignment] = Field(default_factory=list)
    unassigned: list[dict] = Field(default_factory=list)
    baseline: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    generated_at: datetime


class BacktestRequest(BaseModel):
    folds: int = Field(default=4, ge=2, le=12)
    min_train: int = Field(default=30, ge=10, le=5000)


class BacktestFold(BaseModel):
    fold: int
    train_rows: int
    test_rows: int
    period_start: str | None = None
    period_end: str | None = None
    auc: float | None = None
    brier: float | None = None
    ece: float | None = None
    precision_at_10pct: float | None = None


class BacktestResponse(BaseModel):
    folds: list[BacktestFold] = Field(default_factory=list)
    overall: dict[str, float] = Field(default_factory=dict)
    reliability: list[dict] = Field(default_factory=list)
    rows: int = 0
    message: str | None = None
    generated_at: datetime
