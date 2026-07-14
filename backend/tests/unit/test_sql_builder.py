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
    assert "time_start" not in built.params
    assert "time_end" not in built.params
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
    assert "order_date >= DATE_SUB(data_context.data_as_of, INTERVAL 29 DAY)" in built.sql
    assert "GROUP BY week" in built.sql
    assert "ORDER BY week ASC" in built.sql


def test_builder_embeds_data_as_of_context_in_the_single_generated_select():
    built = build_select(QueryIntent(metric="amount", time_range="latest_month"))

    assert "FROM (SELECT MIN(order_date) AS data_start" in built.sql
    assert "MAX(order_date) AS data_as_of FROM sales_order) AS data_context" in built.sql
    assert "LEFT JOIN sales_order ON" in built.sql
    assert "MIN(data_context.data_start) AS _data_start" in built.sql
    assert "MIN(data_context.data_as_of) AS _data_as_of" in built.sql
    assert "COUNT(sales_order.id) AS _match_count" in built.sql
    assert "CURRENT_DATE" not in built.sql


@pytest.mark.parametrize(
    ("metric", "metric_code"),
    [
        ("amount", "sales_amount"),
        ("order_count", "order_count"),
        ("avg_order_value", "average_order_value"),
        ("profit", "profit"),
        ("quantity", "quantity"),
    ],
)
def test_builder_binds_each_intent_metric_to_its_registry_code(metric, metric_code):
    aggregation = "count" if metric == "order_count" else "average" if metric == "avg_order_value" else "sum"

    built = build_select(QueryIntent(metric=metric, aggregation=aggregation))

    assert "metric_definition.metric_code = :metric_code" in built.sql
    assert "metric_definition.enabled = 1" in built.sql
    assert built.params["metric_code"] == metric_code


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
        ("order_count", "count", "COUNT(sales_order.id) AS metric_value"),
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
