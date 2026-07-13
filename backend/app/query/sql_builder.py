import re
from dataclasses import dataclass

from app.core.errors import AppError
from app.query.schemas import QueryIntent


class UnsafeQueryError(AppError):
    def __init__(self, message: str = "查询未通过只读安全校验。") -> None:
        super().__init__(code="UNSAFE_QUERY", message=message, status_code=400)


@dataclass(frozen=True)
class BuiltQuery:
    sql: str
    params: dict[str, str | int]
    display_sql: str


DIMENSIONS = {
    "region": ("region AS region", "region"),
    "province": ("province AS province", "province"),
    "product_name": ("product_name AS product_name", "product_name"),
    "category": ("category AS category", "category"),
    "customer_type": ("customer_type AS customer_type", "customer_type"),
    "month": ("DATE_FORMAT(order_date, '%Y-%m') AS month", "month"),
    "week": ("DATE_FORMAT(order_date, '%x-W%v') AS week", "week"),
}

METRIC_COLUMNS = {"amount": "amount", "quantity": "quantity", "profit": "profit"}

ALLOWED_IDENTIFIERS = {
    "sales_order",
    "id",
    "order_date",
    "region",
    "province",
    "product_name",
    "category",
    "customer_type",
    "quantity",
    "amount",
    "profit",
    "metric_value",
    "month",
    "week",
    "data_context",
    "data_start",
    "data_as_of",
    "_data_start",
    "_data_as_of",
    "_forecast_quantity",
}
ALLOWED_SQL_WORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "AND",
    "GROUP",
    "BY",
    "ORDER",
    "LIMIT",
    "ASC",
    "DESC",
    "AS",
    "SUM",
    "COUNT",
    "AVG",
    "MIN",
    "MAX",
    "DATE_FORMAT",
    "DATE_ADD",
    "DATE_SUB",
    "INTERVAL",
    "MONTH",
    "DAY",
    "CROSS",
    "JOIN",
}
FORBIDDEN_KEYWORDS = {
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DESCRIBE",
    "DROP",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "INSERT",
    "INTO",
    "LOAD",
    "LOCK",
    "MERGE",
    "REPLACE",
    "REVOKE",
    "SET",
    "SHOW",
    "TRUNCATE",
    "UNION",
    "UPDATE",
    "USE",
    "WITH",
}
ALLOWED_STRING_LITERALS = {"%Y-%m-01", "%Y-%m", "%x-W%v"}


def build_select(intent: QueryIntent) -> BuiltQuery:
    intent = _validated_intent(intent)
    select_dimensions = [DIMENSIONS[dimension][0] for dimension in intent.dimensions]
    group_dimensions = [DIMENSIONS[dimension][1] for dimension in intent.dimensions]
    select_parts = [
        *select_dimensions,
        _metric_expression(intent),
        "MIN(data_context.data_start) AS _data_start",
        "MIN(data_context.data_as_of) AS _data_as_of",
    ]
    if _is_forecast(intent):
        select_parts.append("SUM(quantity) AS _forecast_quantity")
    predicates: list[str] = []
    params: dict[str, str | int] = {}

    if intent.time_range != "all":
        predicates.append(_time_predicate(intent.time_range))

    for filter_name, filter_value in intent.filters.items():
        param_name = f"filter_{filter_name}"
        predicates.append(f"{filter_name} = :{param_name}")
        params[param_name] = filter_value

    sql_parts = [
        f"SELECT {', '.join(select_parts)} FROM sales_order "
        "CROSS JOIN (SELECT MIN(order_date) AS data_start, "
        "MAX(order_date) AS data_as_of FROM sales_order) AS data_context"
    ]
    if predicates:
        sql_parts.append(f"WHERE {' AND '.join(predicates)}")
    if group_dimensions:
        sql_parts.append(f"GROUP BY {', '.join(group_dimensions)}")

    order_by = (
        group_dimensions[0]
        if intent.analysis_kind in {"trend", "comparison"} and group_dimensions
        else "metric_value"
    )
    sql_parts.append(f"ORDER BY {order_by} {intent.sort_direction.upper()}")
    sql_parts.append("LIMIT :row_limit")
    params["row_limit"] = intent.limit
    sql = " ".join(sql_parts)
    validate_read_only_sql(sql)
    return BuiltQuery(sql=sql, params=params, display_sql=sql)


def _validated_intent(intent: QueryIntent) -> QueryIntent:
    payload = intent.model_dump() if isinstance(intent, QueryIntent) else intent
    return QueryIntent.model_validate(payload)


def _metric_expression(intent: QueryIntent) -> str:
    if intent.metric == "order_count":
        return "COUNT(id) AS metric_value"
    if intent.metric == "avg_order_value":
        return "AVG(amount) AS metric_value"
    function = {"sum": "SUM", "count": "COUNT", "average": "AVG"}[intent.aggregation]
    return f"{function}({METRIC_COLUMNS[intent.metric]}) AS metric_value"


def _time_predicate(time_range: str) -> str:
    if time_range == "latest_month":
        return (
            "order_date >= DATE_FORMAT(data_context.data_as_of, '%Y-%m-01') "
            "AND order_date < DATE_ADD(DATE_FORMAT(data_context.data_as_of, '%Y-%m-01'), INTERVAL 1 MONTH)"
        )
    if time_range == "previous_month":
        return (
            "order_date >= DATE_SUB(DATE_FORMAT(data_context.data_as_of, '%Y-%m-01'), INTERVAL 1 MONTH) "
            "AND order_date < DATE_FORMAT(data_context.data_as_of, '%Y-%m-01')"
        )
    if time_range == "last_30_days":
        return (
            "order_date >= DATE_SUB(data_context.data_as_of, INTERVAL 29 DAY) "
            "AND order_date < DATE_ADD(data_context.data_as_of, INTERVAL 1 DAY)"
        )
    raise ValueError(f"Unsupported time range: {time_range}")


def _is_forecast(intent: QueryIntent) -> bool:
    return (
        intent.metric == "amount"
        and intent.dimensions == ["month"]
        and intent.time_range == "all"
        and intent.analysis_kind == "trend"
    )


def validate_read_only_sql(sql: str) -> None:
    normalized = sql.strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    if not normalized or not re.match(r"^SELECT\b", normalized, flags=re.IGNORECASE):
        raise UnsafeQueryError()
    if ";" in normalized or re.search(r"--|#|/\*|\*/", normalized):
        raise UnsafeQueryError()
    if re.search(r"\*", normalized):
        raise UnsafeQueryError()
    if len(re.findall(r"\bSELECT\b", normalized, flags=re.IGNORECASE)) != 2:
        raise UnsafeQueryError()
    if len(re.findall(r"\bJOIN\b", normalized, flags=re.IGNORECASE)) != 1:
        raise UnsafeQueryError()
    if not re.search(r"\bFROM\s+sales_order\s+CROSS\s+JOIN\b", normalized, flags=re.IGNORECASE):
        raise UnsafeQueryError()
    if not re.search(
        r"CROSS\s+JOIN\s*\(SELECT\s+MIN\(order_date\)\s+AS\s+data_start,\s*"
        r"MAX\(order_date\)\s+AS\s+data_as_of\s+FROM\s+sales_order\)\s+AS\s+data_context",
        normalized,
        flags=re.IGNORECASE,
    ):
        raise UnsafeQueryError()

    string_literals = re.findall(r"'([^']*)'", normalized)
    if any(value not in ALLOWED_STRING_LITERALS for value in string_literals):
        raise UnsafeQueryError()

    sql_without_values = re.sub(r"'[^']*'|:[A-Za-z_][A-Za-z0-9_]*", " ", normalized)
    words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", sql_without_values)
    for word in words:
        upper_word = word.upper()
        if upper_word in FORBIDDEN_KEYWORDS:
            raise UnsafeQueryError()
        if word not in ALLOWED_IDENTIFIERS and upper_word not in ALLOWED_SQL_WORDS:
            raise UnsafeQueryError()
