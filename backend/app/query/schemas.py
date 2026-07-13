from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MetricCode = Literal["amount", "quantity", "order_count", "avg_order_value", "profit"]
DimensionCode = Literal[
    "region",
    "province",
    "product_name",
    "category",
    "customer_type",
    "month",
    "week",
]

FILTER_CODES = {"region", "province", "product_name", "category", "customer_type"}


class QueryIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: MetricCode
    aggregation: Literal["sum", "count", "average"] = "sum"
    dimensions: list[DimensionCode] = Field(default_factory=list, max_length=2)
    time_range: Literal["all", "latest_month", "previous_month", "last_30_days"] = (
        "latest_month"
    )
    filters: dict[str, str] = Field(default_factory=dict)
    sort_direction: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=20, ge=1, le=100)
    analysis_kind: Literal["ranking", "trend", "comparison", "detail"] = "ranking"

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, filters: dict[str, str]) -> dict[str, str]:
        unknown_filters = set(filters).difference(FILTER_CODES)
        if unknown_filters:
            raise ValueError(f"Unsupported filters: {sorted(unknown_filters)}")
        if any(not isinstance(value, str) or not value.strip() for value in filters.values()):
            raise ValueError("Filter values must be non-empty strings")
        return filters


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_question(cls, question: str) -> str:
        stripped = question.strip()
        if not stripped:
            raise ValueError("Question must not be blank")
        return stripped


class QueryResult(BaseModel):
    intent: QueryIntent
    engine: Literal["local", "ai"]
    safe: bool
    sql: str
    rows: list[dict[str, Any]]
    chart_type: Literal["bar", "line"]
    summary: str
