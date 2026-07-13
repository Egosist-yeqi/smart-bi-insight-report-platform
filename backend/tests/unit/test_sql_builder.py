import pytest

from app.query.schemas import QueryIntent
from app.query.sql_builder import UnsafeQueryError, build_select, validate_read_only_sql


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
    assert built.params == {"filter_region": "华东' OR 1=1 --", "row_limit": 1}
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

    assert "DATE_FORMAT(order_date" in built.sql
    assert "GROUP BY week" in built.sql
    assert "ORDER BY week ASC" in built.sql


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
