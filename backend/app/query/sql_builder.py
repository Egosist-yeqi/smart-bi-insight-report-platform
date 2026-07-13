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

METRICS = {
    "amount": "SUM(amount) AS metric_value",
    "quantity": "SUM(quantity) AS metric_value",
    "order_count": "COUNT(id) AS metric_value",
    "avg_order_value": "AVG(amount) AS metric_value",
    "profit": "SUM(profit) AS metric_value",
}

TIME_PREDICATES = {
    "all": "",
    "latest_month": (
        "order_date >= DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH), '%Y-%m-01') "
        "AND order_date < DATE_FORMAT(CURRENT_DATE, '%Y-%m-01')"
    ),
    "previous_month": (
        "order_date >= DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 2 MONTH), '%Y-%m-01') "
        "AND order_date < DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH), '%Y-%m-01')"
    ),
    "last_30_days": "order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)",
}

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
    "DATE_FORMAT",
    "DATE_SUB",
    "CURRENT_DATE",
    "INTERVAL",
    "MONTH",
    "DAY",
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
    "JOIN",
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
    select_dimensions = [DIMENSIONS[dimension][0] for dimension in intent.dimensions]
    group_dimensions = [DIMENSIONS[dimension][1] for dimension in intent.dimensions]
    select_parts = [*select_dimensions, METRICS[intent.metric]]
    predicates = [TIME_PREDICATES[intent.time_range]] if TIME_PREDICATES[intent.time_range] else []
    params: dict[str, str | int] = {}

    for filter_name, filter_value in intent.filters.items():
        param_name = f"filter_{filter_name}"
        predicates.append(f"{filter_name} = :{param_name}")
        params[param_name] = filter_value

    sql_parts = [f"SELECT {', '.join(select_parts)} FROM sales_order"]
    if predicates:
        sql_parts.append(f"WHERE {' AND '.join(predicates)}")
    if group_dimensions:
        sql_parts.append(f"GROUP BY {', '.join(group_dimensions)}")

    order_by = group_dimensions[0] if intent.analysis_kind == "trend" and group_dimensions else "metric_value"
    sql_parts.append(f"ORDER BY {order_by} {intent.sort_direction.upper()}")
    sql_parts.append("LIMIT :row_limit")
    params["row_limit"] = intent.limit
    sql = " ".join(sql_parts)
    validate_read_only_sql(sql)
    return BuiltQuery(sql=sql, params=params, display_sql=sql)


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
    if len(re.findall(r"\bSELECT\b", normalized, flags=re.IGNORECASE)) != 1:
        raise UnsafeQueryError()
    if not re.search(r"\bFROM\s+sales_order\b", normalized, flags=re.IGNORECASE):
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
