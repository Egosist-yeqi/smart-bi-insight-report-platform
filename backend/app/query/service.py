import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from pydantic import ValidationError
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
PROMOTION_INCREASE = Decimal("0.10")
PROMOTION_ELASTICITY = Decimal("0.42")
PRICE_DROP = Decimal("0.05")
PRICE_ELASTICITY = Decimal("0.68")


class InvalidQueryIntentError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="INVALID_QUERY_INTENT",
            message="查询意图无效，无法执行查询。",
            status_code=400,
        )


@dataclass(frozen=True)
class DataContext:
    data_start: date | None
    data_as_of: date | None


def run_query(
    session: Session,
    question: str,
    resolver: Callable[[str], QueryIntent | dict[str, Any]] | None = None,
) -> QueryResult:
    started_at = time.perf_counter()
    engine = "ai" if resolver is not None else "local"
    intent: QueryIntent | None = None
    built: BuiltQuery | None = None
    fallback_notice: str | None = None

    try:
        try:
            resolved_intent = (
                resolver(question) if resolver is not None else parse_local(question)
            )
        except AppError as exc:
            if resolver is None or not exc.code.startswith("AI_"):
                raise
            engine = "local"
            fallback_notice = "AI 服务不可用，已使用本地规则解析。"
            resolved_intent = parse_local(question)
        intent = _validated_intent(resolved_intent)
        built = build_select(intent)
        timeout_ms = get_settings().query_timeout_seconds * 1000
        session.execute(
            text("SET SESSION MAX_EXECUTION_TIME = :timeout_ms"),
            {"timeout_ms": timeout_ms},
        )
        raw_rows = [dict(row) for row in session.execute(text(built.sql), built.params).mappings()]
        context, rows = _extract_context(raw_rows)
        rows, answer, summary = _answer(intent, rows, context)
        if fallback_notice:
            summary = f"{summary}{fallback_notice}"
        chart_type = "line" if _answer_kind(intent) in {"week_over_week", "forecast"} or set(
            intent.dimensions
        ).intersection({"month", "week"}) else "bar"
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
            rows=_json_safe(rows),
            chart_type=chart_type,
            summary=summary,
            data_as_of=context.data_as_of,
            data_period=_data_period(context),
            query_period=_query_period(intent, context),
            answer=_json_safe(answer),
        )
    except ValidationError as exc:
        _record_failure(
            session,
            question=question,
            engine=engine,
            intent=intent,
            built=built,
            error_code="INVALID_QUERY_INTENT",
            started_at=started_at,
        )
        raise InvalidQueryIntentError() from exc
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


def _validated_intent(value: QueryIntent | dict[str, Any]) -> QueryIntent:
    payload = value.model_dump() if isinstance(value, QueryIntent) else value
    return QueryIntent.model_validate(payload)


def _extract_context(rows: list[dict[str, Any]]) -> tuple[DataContext, list[dict[str, Any]]]:
    if not rows:
        return DataContext(data_start=None, data_as_of=None), []
    context = DataContext(
        data_start=rows[0].get("_data_start"),
        data_as_of=rows[0].get("_data_as_of"),
    )
    business_rows = [
        {
            key: value
            for key, value in row.items()
            if key not in {"_data_start", "_data_as_of", "_match_count"}
        }
        for row in rows
        if int(row.get("_match_count") or 0) > 0
    ]
    return context, business_rows


def _answer(
    intent: QueryIntent, rows: list[dict[str, Any]], context: DataContext
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str]:
    answer_kind = _answer_kind(intent)
    if not rows:
        return [], _empty_answer(answer_kind, intent), _summary(intent, rows, context)
    if answer_kind == "week_over_week":
        answer, comparison_rows = _week_over_week(rows)
        return comparison_rows, answer, _week_summary(answer, context)
    if answer_kind == "forecast":
        answer, forecast_rows = _forecast_answer(rows)
        return forecast_rows, answer, _forecast_summary(answer, context)
    if answer_kind == "promotion_scenario":
        answer, scenario_rows = _scenario_answer(intent, rows)
        return scenario_rows, answer, _scenario_summary(answer, context)
    return rows, None, _summary(intent, rows, context)


def _empty_answer(answer_kind: str | None, intent: QueryIntent) -> dict[str, Any] | None:
    if answer_kind == "week_over_week":
        return {
            "kind": "week_over_week",
            "direction": "unavailable",
            "current": None,
            "previous": None,
            "percent_change": None,
        }
    if answer_kind == "forecast":
        return {"kind": "forecast", "prediction": None}
    if answer_kind == "promotion_scenario":
        return {
            "kind": "promotion_scenario",
            "region": intent.filters["region"],
            "unavailable": True,
        }
    return None


def _answer_kind(intent: QueryIntent) -> str | None:
    if (
        intent.metric == "order_count"
        and intent.dimensions == ["week"]
        and intent.analysis_kind == "comparison"
    ):
        return "week_over_week"
    if (
        intent.metric == "amount"
        and intent.dimensions == ["month"]
        and intent.time_range == "all"
        and intent.analysis_kind == "trend"
    ):
        return "forecast"
    if (
        intent.metric == "amount"
        and intent.dimensions == ["region"]
        and intent.analysis_kind == "detail"
        and "region" in intent.filters
    ):
        return "promotion_scenario"
    return None


def _week_over_week(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chronological_rows = list(reversed(rows))
    if len(chronological_rows) < 2:
        return (
            {
                "kind": "week_over_week",
                "direction": "unavailable",
                "current": chronological_rows[-1] if chronological_rows else None,
                "previous": None,
                "percent_change": None,
            },
            chronological_rows,
        )
    previous, current = chronological_rows[-2:]
    previous_value = Decimal(str(previous["metric_value"]))
    current_value = Decimal(str(current["metric_value"]))
    change = current_value - previous_value
    percent_change = change / previous_value if previous_value else None
    direction = "decrease" if change < 0 else "increase" if change > 0 else "unchanged"
    return (
        {
            "kind": "week_over_week",
            "direction": direction,
            "current": current,
            "previous": previous,
            "absolute_change": change,
            "percent_change": percent_change,
        },
        chronological_rows,
    )


def _forecast_answer(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    history = [
        {
            "month": date.fromisoformat(f"{row['month']}-01"),
            "amount": Decimal(str(row["metric_value"])),
            "quantity": int(row.get("_forecast_quantity") or 0),
            "is_estimate": False,
        }
        for row in rows
    ]
    if not history:
        return {"kind": "forecast", "prediction": None}, history

    sample_count = len(history)
    count = Decimal(sample_count)
    x_sum = sum((Decimal(index) for index in range(sample_count)), Decimal("0"))
    y_sum = sum((point["amount"] for point in history), Decimal("0"))
    xy_sum = sum(
        (Decimal(index) * point["amount"] for index, point in enumerate(history)),
        Decimal("0"),
    )
    x_squared_sum = sum(
        (Decimal(index * index) for index in range(sample_count)), Decimal("0")
    )
    denominator = x_squared_sum - (x_sum * x_sum / count)
    slope = (xy_sum - (x_sum * y_sum / count)) / denominator if denominator else Decimal("0")
    intercept = y_sum / count - slope * x_sum / count
    predicted_amount = (intercept + slope * count).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    prediction = {
        "month": _next_month(history[-1]["month"]),
        "amount": predicted_amount,
        "is_estimate": True,
        "basis": (
            f"使用{sample_count}个种子月度销售额进行普通最小二乘（OLS）线性回归；"
            f"斜率为{slope.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}元/月。"
        ),
    }
    chart_rows = [*history, {**prediction, "quantity": None}]
    return {"kind": "forecast", "prediction": prediction}, chart_rows


def _scenario_answer(
    intent: QueryIntent, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base_amount = Decimal(str(rows[0]["metric_value"])) if rows else Decimal("0")
    promotion_effect = PROMOTION_INCREASE * PROMOTION_ELASTICITY
    price_effect = -(PRICE_DROP * PRICE_ELASTICITY)
    net_change = promotion_effect + price_effect
    simulated_amount = (base_amount * (Decimal("1") + net_change)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    region = intent.filters["region"]
    assumptions = {
        "promotion_increase": PROMOTION_INCREASE,
        "promotion_elasticity": PROMOTION_ELASTICITY,
        "price_drop": PRICE_DROP,
        "price_elasticity": PRICE_ELASTICITY,
    }
    answer = {
        "kind": "promotion_scenario",
        "is_estimate": True,
        "region": region,
        "assumptions": assumptions,
        "base_amount": base_amount,
        "net_change": net_change,
        "simulated_amount": simulated_amount,
    }
    return answer, [answer]


def _summary(intent: QueryIntent, rows: list[dict[str, Any]], context: DataContext) -> str:
    metric_label = METRIC_LABELS[intent.metric]
    prefix = _summary_prefix(context)
    if not rows:
        if context.data_as_of is None:
            return f"当前数据集为空；暂无可用订单数据，无法查询{metric_label}。"
        return f"{prefix}未查询到符合条件的{metric_label}数据。"
    dimension_labels = "、".join(DIMENSION_LABELS[item] for item in intent.dimensions)
    if intent.analysis_kind == "ranking" and intent.dimensions:
        first_dimension = intent.dimensions[0]
        leading_value = rows[0].get(first_dimension)
        leading_metric = rows[0].get("metric_value")
        return (
            f"{prefix}已返回{len(rows)}条{metric_label}数据，排名第一的"
            f"{DIMENSION_LABELS[first_dimension]}为{leading_value}，{metric_label}为{leading_metric}。"
        )
    if dimension_labels:
        return f"{prefix}已返回{len(rows)}条{metric_label}数据，按{dimension_labels}汇总。"
    return f"{prefix}已返回{len(rows)}条{metric_label}数据。"


def _week_summary(answer: dict[str, Any], context: DataContext) -> str:
    prefix = _summary_prefix(context)
    if answer["direction"] == "unavailable":
        return f"{prefix}最近可用周数据不足，无法完成周环比判断。"
    current = answer["current"]
    previous = answer["previous"]
    labels = {"decrease": "下降", "increase": "增长", "unchanged": "持平"}
    direction = labels[answer["direction"]]
    percentage = abs(answer["percent_change"] or Decimal("0")) * 100
    return (
        f"{prefix}最近可用周（{current['week']}）订单量为{current['metric_value']}，"
        f"较上一可用周（{previous['week']}）{direction}{percentage:.2f}%。"
    )


def _forecast_summary(answer: dict[str, Any], context: DataContext) -> str:
    prefix = _summary_prefix(context)
    prediction = answer["prediction"]
    if prediction is None:
        return f"{prefix}历史数据不足，无法生成下月销售额预测。"
    return (
        f"{prefix}预计{prediction['month']}销售额约为{prediction['amount']}。"
        f"{prediction['basis']}预测仅供经营分析参考。"
    )


def _scenario_summary(answer: dict[str, Any], context: DataContext) -> str:
    assumptions = answer["assumptions"]
    return (
        f"{_summary_prefix(context)}这是演示情景估算，并非实际观测结果："
        f"假设{answer['region']}促销投入增加{assumptions['promotion_increase']:.0%}"
        f"（弹性{assumptions['promotion_elasticity']:.2f}），价格下降{assumptions['price_drop']:.0%}"
        f"（弹性{assumptions['price_elasticity']:.2f}），净影响为{answer['net_change']:.2%}，"
        f"模拟销售额为{answer['simulated_amount']}。"
    )


def _data_period(context: DataContext) -> str:
    if context.data_start is None or context.data_as_of is None:
        return "暂无可用数据"
    return f"数据范围{context.data_start.isoformat()}至{context.data_as_of.isoformat()}"


def _query_period(intent: QueryIntent, context: DataContext) -> str:
    if context.data_as_of is None:
        return "暂无可用数据"
    data_as_of = context.data_as_of
    if intent.time_range == "all":
        return _data_period(context)
    if intent.time_range == "latest_month":
        return f"{data_as_of:%Y-%m}"
    if intent.time_range == "previous_month":
        previous = date(
            data_as_of.year - (data_as_of.month == 1),
            (data_as_of.month - 2) % 12 + 1,
            1,
        )
        return f"{previous:%Y-%m}"
    return f"{(data_as_of - date.resolution * 29).isoformat()}至{data_as_of.isoformat()}"


def _summary_prefix(context: DataContext) -> str:
    if context.data_as_of is None:
        return "当前数据集为空；"
    return f"数据截至{context.data_as_of.isoformat()}（{_data_period(context)}）；"


def _next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _record_failure(
    session: Session,
    *,
    question: str,
    engine: str,
    intent: QueryIntent | None,
    built: BuiltQuery | None,
    error_code: str,
    started_at: float,
) -> None:
    if session.in_transaction():
        session.rollback()
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


def _duration_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))
