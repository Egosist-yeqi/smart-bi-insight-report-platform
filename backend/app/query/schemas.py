from typing import Any, Literal

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
COMPATIBLE_AGGREGATIONS = {
    "amount": {"sum", "count", "average"},
    "quantity": {"sum", "count", "average"},
    "profit": {"sum", "count", "average"},
    "order_count": {"count"},
    "avg_order_value": {"average"},
}


class QueryIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)

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

    @model_validator(mode="after")
    def validate_metric_aggregation(self) -> "QueryIntent":
        if self.aggregation not in COMPATIBLE_AGGREGATIONS[self.metric]:
            raise ValueError(
                f"Aggregation {self.aggregation!r} is incompatible with metric {self.metric!r}"
            )
        return self


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

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
    data_as_of: date | None
    data_period: str
    query_period: str
    answer: dict[str, Any] | None = None
