from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ActionPriority = Literal["high", "medium", "low"]
ActionStatus = Literal["open", "in_progress", "completed"]
ActionSource = Literal["manual", "anomaly", "forecast", "query", "report"]


class ActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=180)
    owner: str | None = Field(default=None, max_length=80)
    priority: ActionPriority = "medium"
    due_date: date | None = None
    target_metric: str | None = Field(default=None, max_length=80)
    source_type: ActionSource = "manual"
    evidence: str | None = Field(default=None, max_length=1200)


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    owner: str | None = Field(default=None, max_length=80)
    priority: ActionPriority | None = None
    status: ActionStatus | None = None
    due_date: date | None = None
    target_metric: str | None = Field(default=None, max_length=80)
    evidence: str | None = Field(default=None, max_length=1200)
    review_notes: str | None = Field(default=None, max_length=1200)


class ActionItem(BaseModel):
    id: int
    title: str
    owner: str | None
    priority: ActionPriority
    status: ActionStatus
    due_date: date | None
    target_metric: str | None
    source_type: ActionSource
    evidence: str | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


class ActionSummary(BaseModel):
    open: int
    in_progress: int
    completed: int
    overdue: int


class ActionListResult(BaseModel):
    items: list[ActionItem]
    summary: ActionSummary
