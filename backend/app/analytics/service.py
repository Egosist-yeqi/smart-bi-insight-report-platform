from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    AnomalyItem,
    AnomalyResult,
    DashboardFilters,
    DashboardResult,
    ForecastPrediction,
    ForecastResult,
    KpiDeltas,
    Kpis,
    MetadataResult,
    MetricDefinitionData,
    RankingPoint,
    TrendPoint,
)
from app.db.models import MetricDefinition, SalesOrder

ZERO = Decimal("0")
ANOMALY_THRESHOLD = Decimal("0.18")


@dataclass(frozen=True)
class _MonthlyAggregate:
    month: date
    amount: Decimal
    quantity: int
    profit: Decimal
    order_count: int


def _decimal(value: Decimal | int | None) -> Decimal:
    return Decimal(value or ZERO)


def _next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _previous_month(month: date) -> date:
    return date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)


def _predicates(filters: DashboardFilters) -> list:
    predicates = []
    if filters.region is not None:
        predicates.append(SalesOrder.region == filters.region)
    if filters.category is not None:
        predicates.append(SalesOrder.category == filters.category)
    if filters.customer_type is not None:
        predicates.append(SalesOrder.customer_type == filters.customer_type)
    return predicates


def _kpis(session: Session, filters: DashboardFilters) -> Kpis:
    amount = func.coalesce(func.sum(SalesOrder.amount), ZERO)
    quantity = func.coalesce(func.sum(SalesOrder.quantity), 0)
    order_count = func.count(SalesOrder.id)
    average_order_value = func.coalesce(amount / func.nullif(order_count, 0), ZERO)
    profit_rate = func.coalesce(
        func.sum(SalesOrder.profit) / func.nullif(func.sum(SalesOrder.amount), 0), ZERO
    )
    row = session.execute(
        select(
            amount.label("amount"),
            quantity.label("quantity"),
            average_order_value.label("avg_order_value"),
            profit_rate.label("profit_rate"),
        ).where(*_predicates(filters))
    ).one()
    return Kpis(
        amount=_decimal(row.amount),
        quantity=int(row.quantity or 0),
        avg_order_value=_decimal(row.avg_order_value),
        profit_rate=_decimal(row.profit_rate),
    )


def _monthly_aggregates(
    session: Session, filters: DashboardFilters
) -> list[_MonthlyAggregate]:
    year = func.year(SalesOrder.order_date)
    month = func.month(SalesOrder.order_date)
    rows = session.execute(
        select(
            year.label("year"),
            month.label("month"),
            func.coalesce(func.sum(SalesOrder.amount), ZERO).label("amount"),
            func.coalesce(func.sum(SalesOrder.quantity), 0).label("quantity"),
            func.coalesce(func.sum(SalesOrder.profit), ZERO).label("profit"),
            func.count(SalesOrder.id).label("order_count"),
        )
        .where(*_predicates(filters))
        .group_by(year, month)
        .order_by(year, month)
    )
    return [
        _MonthlyAggregate(
            month=date(int(row.year), int(row.month), 1),
            amount=_decimal(row.amount),
            quantity=int(row.quantity or 0),
            profit=_decimal(row.profit),
            order_count=int(row.order_count or 0),
        )
        for row in rows
    ]


def _monthly_kpis(month: _MonthlyAggregate) -> Kpis:
    average_order_value = (
        month.amount / month.order_count if month.order_count else ZERO
    )
    profit_rate = month.profit / month.amount if month.amount else ZERO
    return Kpis(
        amount=month.amount,
        quantity=month.quantity,
        avg_order_value=average_order_value,
        profit_rate=profit_rate,
    )


def _percent_delta(current: Decimal | int, previous: Decimal | int) -> Decimal:
    previous_value = _decimal(previous)
    if not previous_value:
        return ZERO
    return (_decimal(current) - previous_value) / previous_value


def _deltas(months: list[_MonthlyAggregate]) -> KpiDeltas:
    if len(months) < 2:
        return KpiDeltas(
            amount=ZERO, quantity=ZERO, avg_order_value=ZERO, profit_rate=ZERO
        )
    current = _monthly_kpis(months[-1])
    previous = _monthly_kpis(months[-2])
    return KpiDeltas(
        amount=_percent_delta(current.amount, previous.amount),
        quantity=_percent_delta(current.quantity, previous.quantity),
        avg_order_value=_percent_delta(
            current.avg_order_value, previous.avg_order_value
        ),
        profit_rate=current.profit_rate - previous.profit_rate,
    )


def _ranking(
    session: Session, filters: DashboardFilters, dimension, *group_by
) -> list[RankingPoint]:
    amount = func.coalesce(func.sum(SalesOrder.amount), ZERO)
    profit = func.coalesce(func.sum(SalesOrder.profit), ZERO)
    order_count = func.count(SalesOrder.id)
    rows = session.execute(
        select(
            dimension.label("name"),
            amount.label("amount"),
            func.coalesce(func.sum(SalesOrder.quantity), 0).label("quantity"),
            profit.label("profit"),
            order_count.label("order_count"),
            func.coalesce(profit / func.nullif(amount, 0), ZERO).label("profit_rate"),
        )
        .where(*_predicates(filters))
        .group_by(*group_by)
        .order_by(amount.desc(), dimension.asc())
    )
    return [
        RankingPoint(
            name=row.name,
            amount=_decimal(row.amount),
            quantity=int(row.quantity or 0),
            profit=_decimal(row.profit),
            order_count=int(row.order_count or 0),
            profit_rate=_decimal(row.profit_rate),
        )
        for row in rows
    ]


def get_metadata(session: Session) -> MetadataResult:
    metrics = session.scalars(
        select(MetricDefinition)
        .where(MetricDefinition.enabled.is_(True))
        .order_by(MetricDefinition.metric_code)
    )

    def values(column) -> list[str]:
        return list(session.scalars(select(column).distinct().order_by(column)))

    return MetadataResult(
        metrics=[
            MetricDefinitionData(
                metric_name=metric.metric_name,
                metric_code=metric.metric_code,
                formula=metric.formula,
                description=metric.description,
                enabled=metric.enabled,
            )
            for metric in metrics
        ],
        regions=values(SalesOrder.region),
        categories=values(SalesOrder.category),
        customer_types=values(SalesOrder.customer_type),
    )


def get_dashboard(session: Session, filters: DashboardFilters) -> DashboardResult:
    months = _monthly_aggregates(session, filters)
    return DashboardResult(
        kpis=_kpis(session, filters),
        deltas=_deltas(months),
        trend=[
            TrendPoint(month=month.month, amount=month.amount, quantity=month.quantity)
            for month in months
        ],
        regions=_ranking(session, filters, SalesOrder.region, SalesOrder.region),
        products=_ranking(
            session,
            filters,
            SalesOrder.product_name,
            SalesOrder.product_id,
            SalesOrder.product_name,
        ),
        filters=filters,
    )


def _region_amounts(session: Session, month: date) -> dict[str, Decimal]:
    return {
        row.region: _decimal(row.amount)
        for row in session.execute(
            select(
                SalesOrder.region,
                func.coalesce(func.sum(SalesOrder.amount), ZERO).label("amount"),
            )
            .where(
                SalesOrder.order_date >= month,
                SalesOrder.order_date < _next_month(month),
            )
            .group_by(SalesOrder.region)
            .order_by(SalesOrder.region)
        )
    }


def detect_anomalies(
    session: Session, *, as_of: date | None = None
) -> AnomalyResult:
    effective_as_of = as_of or date.today()
    current_month = date(effective_as_of.year, effective_as_of.month, 1)
    latest_month = _previous_month(current_month)
    previous_month = _previous_month(latest_month)
    previous = _region_amounts(session, previous_month)
    current = _region_amounts(session, latest_month)
    if not previous or not current:
        return AnomalyResult(items=[])

    items = []
    for region in sorted(current):
        previous_value = previous.get(region, ZERO)
        current_value = current[region]
        delta = _percent_delta(current_value, previous_value)
        if not previous_value or abs(delta) < ANOMALY_THRESHOLD:
            continue
        direction = "下降" if delta < ZERO else "增长"
        items.append(
            AnomalyItem(
                metric="销售额",
                region=region,
                current_value=current_value,
                previous_value=previous_value,
                delta=delta,
                level="下降预警" if delta < ZERO else "增长提醒",
                evidence=(
                    f"{latest_month:%Y-%m}销售额为{current_value}，"
                    f"较{previous_month:%Y-%m}的{previous_value}{direction}"
                    f"{abs(delta):.2%}，达到18%阈值。"
                ),
                inference=(
                    f"基于种子订单的月度区域聚合，{region}存在显著销售额{direction}；"
                    "应进一步核查产品组合、客户订单与出货节奏。"
                ),
            )
        )
    return AnomalyResult(
        items=sorted(items, key=lambda item: (-abs(item.delta), item.region))
    )


def forecast_next_month(
    session: Session, *, through_month: date | None = None
) -> ForecastResult:
    months = _monthly_aggregates(session, DashboardFilters())
    if through_month is not None:
        cutoff = date(through_month.year, through_month.month, 1)
        months = [month for month in months if month.month <= cutoff]
    history = [
        TrendPoint(month=month.month, amount=month.amount, quantity=month.quantity)
        for month in months
    ]
    if not months:
        return ForecastResult(history=[], prediction=None)

    sample_count = len(months)
    count = Decimal(sample_count)
    x_sum = sum((Decimal(index) for index in range(sample_count)), ZERO)
    y_sum = sum((month.amount for month in months), ZERO)
    xy_sum = sum(
        (Decimal(index) * month.amount for index, month in enumerate(months)), ZERO
    )
    x_squared_sum = sum(
        (Decimal(index * index) for index in range(sample_count)), ZERO
    )
    denominator = x_squared_sum - (x_sum * x_sum / count)
    slope = (xy_sum - (x_sum * y_sum / count)) / denominator if denominator else ZERO
    intercept = y_sum / count - slope * x_sum / count
    predicted_amount = (intercept + slope * count).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    next_month = _next_month(months[-1].month)
    return ForecastResult(
        history=history,
        prediction=ForecastPrediction(
            month=next_month,
            amount=predicted_amount,
            is_estimate=True,
            basis=(
                f"使用{sample_count}个种子月度销售额进行普通最小二乘（OLS）线性回归；"
                f"斜率为{slope.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}元/月。"
            ),
        ),
    )
