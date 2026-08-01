from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DashboardFilters(BaseModel):
    region: str | None = None
    category: str | None = None
    customer_type: str | None = None


class MetricDefinitionData(BaseModel):
    metric_name: str
    metric_code: str
    formula: str
    description: str
    enabled: bool


class DataScopeData(BaseModel):
    records: int
    start_date: date | None
    end_date: date | None
    months: int


class MetadataResult(BaseModel):
    metrics: list[MetricDefinitionData]
    regions: list[str]
    categories: list[str]
    customer_types: list[str]
    data_scope: DataScopeData


class Kpis(BaseModel):
    amount: Decimal
    quantity: int
    avg_order_value: Decimal
    profit_rate: Decimal


class KpiDeltas(BaseModel):
    amount: Decimal
    quantity: Decimal
    avg_order_value: Decimal
    profit_rate: Decimal


class TrendPoint(BaseModel):
    month: date
    amount: Decimal
    quantity: int


class RankingPoint(BaseModel):
    name: str
    amount: Decimal
    quantity: int
    profit: Decimal
    order_count: int
    profit_rate: Decimal


class DashboardResult(BaseModel):
    kpis: Kpis
    deltas: KpiDeltas
    trend: list[TrendPoint]
    regions: list[RankingPoint]
    products: list[RankingPoint]
    filters: DashboardFilters


class AnomalyItem(BaseModel):
    metric: str
    region: str
    current_value: Decimal
    previous_value: Decimal
    delta: Decimal
    level: str
    evidence: str
    inference: str


class AnomalyResult(BaseModel):
    items: list[AnomalyItem]


class ForecastPrediction(BaseModel):
    month: date
    amount: Decimal
    is_estimate: bool
    basis: str


class ForecastResult(BaseModel):
    history: list[TrendPoint]
    prediction: ForecastPrediction | None
