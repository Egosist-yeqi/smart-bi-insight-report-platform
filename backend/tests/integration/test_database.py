from sqlalchemy import func, select

from app.db.models import MetricDefinition, SalesOrder
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
    rows = db_session.scalars(select(SalesOrder)).all()

    assert min(row.order_date for row in rows).isoformat().startswith("2025-01")
    assert max(row.order_date for row in rows).isoformat().startswith("2026-06")
    assert len({row.region for row in rows}) == 5
    assert len({row.product_id for row in rows}) == 6
