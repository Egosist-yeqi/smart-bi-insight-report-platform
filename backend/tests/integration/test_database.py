from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, inspect, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.db.models import AIProviderConfig, MetricDefinition, ReportTemplate, SalesOrder
from app.db.seed import seed_database


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
