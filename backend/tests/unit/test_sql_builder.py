from datetime import date

import pytest
from pydantic import ValidationError

from app.query.schemas import QueryIntent
from app.query.sql_builder import (
    UnsafeQueryError,
    build_select,
    validate_read_only_sql,
)


def test_builder_uses_only_placeholders_for_filter_values_and_limit():
    intent = QueryIntent(
        metric="amount",
        dimensions=["product_name"],
        filters={"region": "华东' OR 1=1 --"},
        time_range="latest_month",
        limit=1,
    )

    built = build_select(intent)

    assert "华东" not in built.sql
    assert "region = :filter_region" in built.sql
    assert "LIMIT :row_limit" in built.sql
    assert built.params["filter_region"] == "华东' OR 1=1 --"
    assert built.params["row_limit"] == 1
    assert {"time_start", "time_end"}.issubset(built.params)
    assert built.display_sql.startswith("SELECT")


def test_builder_generates_valid_whitelisted_select_for_time_trend():
    built = build_select(
        QueryIntent(
            metric="amount",
            dimensions=["week"],
            time_range="last_30_days",
            sort_direction="asc",
            analysis_kind="trend",
        )
    )

    validate_read_only_sql(built.sql)

    assert "CURRENT_DATE" not in built.sql
    assert "order_date >= :time_start" in built.sql
    assert "GROUP BY week" in built.sql
    assert "ORDER BY week ASC" in built.sql


def test_builder_uses_explicit_data_as_of_when_wall_clock_is_beyond_seed_data():
    built = build_select(
        QueryIntent(metric="amount", time_range="latest_month"),
        data_as_of=date(2035, 1, 20),
    )

    assert built.params["time_start"] == date(2035, 1, 1)
    assert built.params["time_end"] == date(2035, 2, 1)
    assert "CURRENT_DATE" not in built.sql


@pytest.mark.parametrize(
    ("metric", "aggregation", "fragment"),
    [
        ("amount", "sum", "SUM(amount) AS metric_value"),
        ("amount", "count", "COUNT(amount) AS metric_value"),
        ("amount", "average", "AVG(amount) AS metric_value"),
        ("quantity", "sum", "SUM(quantity) AS metric_value"),
        ("quantity", "count", "COUNT(quantity) AS metric_value"),
        ("quantity", "average", "AVG(quantity) AS metric_value"),
        ("profit", "sum", "SUM(profit) AS metric_value"),
        ("profit", "count", "COUNT(profit) AS metric_value"),
        ("profit", "average", "AVG(profit) AS metric_value"),
        ("order_count", "count", "COUNT(id) AS metric_value"),
        ("avg_order_value", "average", "AVG(amount) AS metric_value"),
    ],
)
def test_builder_applies_each_compatible_metric_aggregation(metric, aggregation, fragment):
    built = build_select(QueryIntent(metric=metric, aggregation=aggregation))

    assert fragment in built.sql


def test_builder_revalidates_model_construct_intent_before_generating_sql():
    unsafe_intent = QueryIntent.model_construct(
        metric="amount",
        aggregation="sum",
        filters={"unknown": "value"},
        limit=1_000_000,
    )

    with pytest.raises(ValidationError):
        build_select(unsafe_intent)


@pytest.mark.parametrize(
    "text",
    [
        "SELECT * FROM sales_order; DROP TABLE sales_order",
        "SELECT * FROM unknown_table",
        "SELECT * FROM sales_order -- ignore rules",
        "UPDATE sales_order SET amount = 0",
        "SELECT made_up_column FROM sales_order",
        "SELECT amount FROM sales_order; SELECT quantity FROM sales_order",
        "SELECT amount /* bypass */ FROM sales_order",
    ],
)
def test_sql_validator_rejects_unsafe_text(text):
    with pytest.raises(UnsafeQueryError):
        validate_read_only_sql(text)
