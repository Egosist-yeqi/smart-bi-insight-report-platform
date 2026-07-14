from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MetricDefinition, ReportTemplate, SalesOrder
from app.db.session import get_engine

REGIONS = (
    ("华东", "上海", Decimal("1.18")),
    ("华南", "广东", Decimal("0.96")),
    ("华北", "北京", Decimal("1.05")),
    ("西南", "四川", Decimal("0.88")),
    ("华中", "湖北", Decimal("0.92")),
)

PRODUCTS = (
    (1, "星云 Pro 智能终端", "智能硬件", Decimal("4900"), Decimal("0.25"), "企业客户"),
    (2, "极光 Mini 传感器", "工业传感", Decimal("1500"), Decimal("0.22"), "渠道客户"),
    (3, "云枢 BI 套件", "软件订阅", Decimal("9000"), Decimal("0.45"), "企业客户"),
    (4, "蓝鲸 Edge 网关", "边缘计算", Decimal("4900"), Decimal("0.23"), "政府客户"),
    (5, "辰星 数据服务包", "数据服务", Decimal("8000"), Decimal("0.36"), "企业客户"),
    (6, "光栅智能工作站", "智能硬件", Decimal("3200"), Decimal("0.28"), "渠道客户"),
)

METRICS = (
    ("销售额", "sales_amount", "SUM(amount)", "指定范围内的销售金额总和"),
    ("销售数量", "quantity", "SUM(quantity)", "指定范围内的销售数量总和"),
    ("订单量", "order_count", "COUNT(*)", "指定范围内的订单记录数"),
    ("客单价", "average_order_value", "SUM(amount) / COUNT(*)", "每笔订单的平均销售金额"),
    ("毛利", "profit", "SUM(profit)", "指定范围内的毛利总和"),
)
LEGACY_PROFIT_MARGIN = (
    "毛利率",
    "SUM(profit) / SUM(amount)",
)

REPORT_TEMPLATES = (
    ("周度经营报告", "weekly", ["overview", "region", "ranking", "anomaly"]),
    ("月度经营报告", "monthly", ["overview", "region", "ranking", "forecast"]),
    ("自定义经营报告", "custom", ["overview", "region", "ranking", "anomaly", "forecast"]),
)


@dataclass(frozen=True)
class SeedResult:
    orders_inserted: int
    metrics_inserted: int
    templates_inserted: int


def _month_starts() -> tuple[date, ...]:
    return tuple(
        date(2025 + month_index // 12, month_index % 12 + 1, 1)
        for month_index in range(18)
    )


def _seed_orders(session: Session) -> int:
    orders: list[SalesOrder] = []
    external_order_ids = {
        f"SEED-{month_start:%Y%m}-{region_index}-{product_id}"
        for month_start in _month_starts()
        for region_index, _region in enumerate(REGIONS)
        for product_id, *_product in PRODUCTS
    }
    existing_ids = set(
        session.scalars(
            select(SalesOrder.external_order_id).where(
                SalesOrder.external_order_id.in_(external_order_ids)
            )
        )
    )

    for month_index, month_start in enumerate(_month_starts()):
        season_factor = Decimal("1.00") + Decimal((month_index % 6) - 2) / Decimal(
            "100"
        )
        for region_index, (region, province, region_multiplier) in enumerate(REGIONS):
            for product_id, name, category, unit_price, margin, customer_type in PRODUCTS:
                external_order_id = (
                    f"SEED-{month_start:%Y%m}-{region_index}-{product_id}"
                )
                if external_order_id in existing_ids:
                    continue
                quantity = 20 + (
                    ((month_index + 1) * 7 + region_index * 11 + product_id * 13) % 181
                )
                amount = (
                    Decimal(quantity) * unit_price * region_multiplier * season_factor
                ).quantize(Decimal("0.01"))
                profit = (amount * margin).quantize(Decimal("0.01"))
                orders.append(
                    SalesOrder(
                        external_order_id=external_order_id,
                        order_date=month_start
                        + timedelta(days=(region_index * 5 + product_id * 3) % 27),
                        region=region,
                        province=province,
                        product_id=product_id,
                        product_name=name,
                        category=category,
                        customer_type=customer_type,
                        quantity=quantity,
                        amount=amount,
                        profit=profit,
                    )
                )
    session.add_all(orders)
    return len(orders)


def _seed_metrics(session: Session) -> int:
    existing_metrics = {
        metric.metric_code: metric
        for metric in session.scalars(select(MetricDefinition))
    }
    legacy_metric = existing_metrics.get("profit_margin")
    if (
        "quantity" not in existing_metrics
        and legacy_metric is not None
        and (legacy_metric.metric_name, legacy_metric.formula) == LEGACY_PROFIT_MARGIN
    ):
        quantity = next(metric for metric in METRICS if metric[1] == "quantity")
        legacy_metric.metric_name = quantity[0]
        legacy_metric.metric_code = quantity[1]
        legacy_metric.formula = quantity[2]
        legacy_metric.description = quantity[3]
        existing_metrics.pop("profit_margin")
        existing_metrics["quantity"] = legacy_metric

    metrics = [
        MetricDefinition(
            metric_name=name,
            metric_code=code,
            formula=formula,
            description=description,
        )
        for name, code, formula, description in METRICS
        if code not in existing_metrics
    ]
    session.add_all(metrics)
    return len(metrics)


def _seed_templates(session: Session) -> int:
    existing_names = set(session.scalars(select(ReportTemplate.template_name)))
    templates = [
        ReportTemplate(
            template_name=name,
            report_type=report_type,
            sections=sections,
        )
        for name, report_type, sections in REPORT_TEMPLATES
        if name not in existing_names
    ]
    session.add_all(templates)
    return len(templates)


def seed_database(session: Session) -> SeedResult:
    orders_inserted = _seed_orders(session)
    metrics_inserted = _seed_metrics(session)
    templates_inserted = _seed_templates(session)
    session.commit()
    return SeedResult(orders_inserted, metrics_inserted, templates_inserted)


def main() -> None:
    with Session(get_engine()) as session:
        result = seed_database(session)
        total_orders = session.scalar(select(func.count()).select_from(SalesOrder))
    print(
        "Seed complete: "
        f"orders_inserted={result.orders_inserted} "
        f"metrics_inserted={result.metrics_inserted} "
        f"templates_inserted={result.templates_inserted} "
        f"total_orders={total_orders}"
    )


if __name__ == "__main__":
    main()
