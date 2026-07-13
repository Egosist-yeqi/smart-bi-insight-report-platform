import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import QueryHistory
from app.query.local_parser import parse_local
from app.query.schemas import QueryIntent, QueryResult
from app.query.sql_builder import BuiltQuery, build_select


METRIC_LABELS = {
    "amount": "销售额",
    "quantity": "销售数量",
    "order_count": "订单量",
    "avg_order_value": "客单价",
    "profit": "毛利",
}
DIMENSION_LABELS = {
    "region": "区域",
    "province": "省份",
    "product_name": "产品",
    "category": "产品类别",
    "customer_type": "客户类型",
    "month": "月份",
    "week": "周",
}


def run_query(
    session: Session,
    question: str,
    resolver: Callable[[str], QueryIntent | dict[str, Any]] | None = None,
) -> QueryResult:
    started_at = time.perf_counter()
    engine = "ai" if resolver is not None else "local"
    intent: QueryIntent | None = None
    built: BuiltQuery | None = None

    try:
        resolved_intent = resolver(question) if resolver is not None else parse_local(question)
        intent = QueryIntent.model_validate(resolved_intent)
        built = build_select(intent)
        timeout_ms = get_settings().query_timeout_seconds * 1000
        session.execute(text("SET SESSION MAX_EXECUTION_TIME = :timeout_ms"), {"timeout_ms": timeout_ms})
        result = session.execute(text(built.sql), built.params)
        rows = [_json_safe(dict(row)) for row in result.mappings()]
        chart_type = "line" if set(intent.dimensions).intersection({"month", "week"}) else "bar"
        summary = _summary(intent, rows)
        _record_history(
            session,
            question=question,
            engine=engine,
            intent=intent,
            built=built,
            summary=summary,
            status="succeeded",
            error_code=None,
            duration_ms=_duration_ms(started_at),
        )
        session.commit()
        return QueryResult(
            intent=intent,
            engine=engine,
            safe=True,
            sql=built.display_sql,
            rows=rows,
            chart_type=chart_type,
            summary=summary,
        )
    except Exception as exc:
        if session.in_transaction():
            session.rollback()
        error_code = exc.code if isinstance(exc, AppError) else "QUERY_EXECUTION_FAILED"
        _record_history(
            session,
            question=question,
            engine=engine,
            intent=intent,
            built=built,
            summary=None,
            status="failed",
            error_code=error_code,
            duration_ms=_duration_ms(started_at),
        )
        session.commit()
        if isinstance(exc, AppError):
            raise
        raise AppError(
            code="QUERY_EXECUTION_FAILED",
            message="查询执行失败，请稍后重试。",
            status_code=500,
        ) from exc


def _record_history(
    session: Session,
    *,
    question: str,
    engine: str,
    intent: QueryIntent | None,
    built: BuiltQuery | None,
    summary: str | None,
    status: str,
    error_code: str | None,
    duration_ms: int,
) -> None:
    session.add(
        QueryHistory(
            question=question,
            engine=engine,
            intent_json=intent.model_dump(mode="json") if intent else None,
            generated_sql=built.display_sql if built else None,
            parameters_json=_json_safe(built.params) if built else None,
            summary=summary,
            status=status,
            error_code=error_code,
            duration_ms=duration_ms,
        )
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _summary(intent: QueryIntent, rows: list[dict[str, Any]]) -> str:
    metric_label = METRIC_LABELS[intent.metric]
    if not rows:
        return f"未查询到符合条件的{metric_label}数据。"
    dimension_labels = "、".join(DIMENSION_LABELS[item] for item in intent.dimensions)
    if intent.analysis_kind == "ranking" and intent.dimensions:
        first_dimension = intent.dimensions[0]
        leading_value = rows[0].get(first_dimension)
        leading_metric = rows[0].get("metric_value")
        return f"已返回{len(rows)}条{metric_label}数据，排名第一的{DIMENSION_LABELS[first_dimension]}为{leading_value}，{metric_label}为{leading_metric}。"
    if dimension_labels:
        return f"已返回{len(rows)}条{metric_label}数据，按{dimension_labels}汇总。"
    return f"已返回{len(rows)}条{metric_label}数据。"


def _duration_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))
