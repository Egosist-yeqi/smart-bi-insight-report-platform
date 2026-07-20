from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.db.models import AIProviderConfig, MetricDefinition, ReportTemplate, SalesOrder
from app.db.seed import seed_database
from app.query.sql_builder import METRIC_REGISTRY_CODES


def test_seed_creates_exactly_540_orders_and_is_idempotent(db_session):
    first = seed_database(db_session)
    second = seed_database(db_session)

    order_count = db_session.scalar(select(func.count()).select_from(SalesOrder))
    metric_count = db_session.scalar(
        select(func.count()).select_from(MetricDefinition)
    )

    assert first.orders_inserted == 540
    assert second.orders_inserted == 0
    assert order_count == 540
    assert metric_count == 5
    assert set(db_session.scalars(select(MetricDefinition.metric_code))) == set(
        METRIC_REGISTRY_CODES.values()
    )


def test_seed_upgrades_obsolete_profit_margin_to_quantity_idempotently(db_session):
    legacy_metrics = (
        ("销售额", "sales_amount", "SUM(amount)", "旧版种子指标"),
        ("订单量", "order_count", "COUNT(*)", "旧版种子指标"),
        ("客单价", "average_order_value", "SUM(amount) / COUNT(*)", "旧版种子指标"),
        ("毛利", "profit", "SUM(profit)", "旧版种子指标"),
        (
            "毛利率",
            "profit_margin",
            "SUM(profit) / SUM(amount)",
            "毛利占销售额的比例",
        ),
    )
    db_session.add_all(
        MetricDefinition(
            metric_name=name,
            metric_code=code,
            formula=formula,
            description=description,
        )
        for name, code, formula, description in legacy_metrics
    )
    db_session.commit()

    upgraded = seed_database(db_session)
    repeated = seed_database(db_session)
    metrics = db_session.scalars(
        select(MetricDefinition).order_by(MetricDefinition.metric_code)
    ).all()

    assert upgraded.metrics_inserted == 0
    assert repeated.metrics_inserted == 0
    assert len(metrics) == 5
    assert {metric.metric_code for metric in metrics} == {
        "sales_amount",
        "quantity",
        "order_count",
        "average_order_value",
        "profit",
    }
    quantity = next(metric for metric in metrics if metric.metric_code == "quantity")
    assert quantity.formula == "SUM(quantity)"


def test_seed_preserves_a_custom_profit_margin_metric(db_session):
    db_session.add(
        MetricDefinition(
            metric_name="毛利率",
            metric_code="profit_margin",
            formula="SUM(profit) / SUM(amount)",
            description="毛利占销售额的比例",
            enabled=False,
        )
    )
    db_session.commit()

    seed_database(db_session)

    custom = db_session.scalar(
        select(MetricDefinition).where(
            MetricDefinition.metric_code == "profit_margin"
        )
    )
    assert custom is not None
    assert custom.metric_name == "毛利率"
    assert custom.formula == "SUM(profit) / SUM(amount)"
    assert custom.description == "毛利占销售额的比例"
    assert custom.enabled is False


def test_seed_covers_required_date_and_dimensions(db_session):
    seed_database(db_session)
    rows = db_session.scalars(select(SalesOrder)).all()

    assert min(row.order_date for row in rows).isoformat().startswith("2025-01")
    assert max(row.order_date for row in rows).isoformat().startswith("2026-06")
    assert len({row.region for row in rows}) == 5
    assert len({row.product_id for row in rows}) == 6


def test_seed_matches_contract_formula_for_known_order(db_session):
    seed_database(db_session)

    order = db_session.scalar(
        select(SalesOrder).where(SalesOrder.external_order_id == "SEED-202501-0-1")
    )

    assert order is not None
    assert order.quantity == 40
    assert order.amount == Decimal("226654.40")
    assert order.profit == Decimal("56663.60")
    assert order.order_date == date(2025, 1, 1) + timedelta(days=3)


def test_updated_at_mysql_ddl_matches_migrated_schema(db_session):
    inspector = inspect(db_session.bind)

    for model in (ReportTemplate, AIProviderConfig):
        model_ddl = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        migrated_ddl = db_session.execute(
            text(f"SHOW CREATE TABLE `{model.__tablename__}`")
        ).one()[1]
        columns = inspector.get_columns(model.__tablename__)
        updated_at = next(column for column in columns if column["name"] == "updated_at")

        assert updated_at["nullable"] is False
        assert "CURRENT_TIMESTAMP" in str(updated_at["default"]).upper()
        assert "ON UPDATE CURRENT_TIMESTAMP" in model_ddl.upper()
        assert "ON UPDATE CURRENT_TIMESTAMP" in migrated_ddl.upper()
