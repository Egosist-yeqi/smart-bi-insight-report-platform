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
from app.core.warnings import ServiceWarning, ai_service_warning
from app.db.models import QueryHistory
from app.query.local_parser import decision_support_kind, parse_local
from app.query.schemas import QueryIntent, QueryResult
from app.query.sql_builder import BuiltQuery, build_select
from app.scenarios.catalog import (
    SCENARIO_BY_ID,
    ScenarioDefinition,
    scenario_for_template_question,
    template_for_question,
)


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


class MetricNotAvailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="METRIC_NOT_AVAILABLE",
            message="该指标未登记或已停用，无法执行查询。",
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
    fallback_warning: ServiceWarning | None = None,
) -> QueryResult:
    started_at = time.perf_counter()
    engine = "ai" if resolver is not None else "local"
    intent: QueryIntent | None = None
    built: BuiltQuery | None = None

    try:
        template = template_for_question(question)
        decision_kind = decision_support_kind(question)
        if template is not None:
            resolved_intent = QueryIntent.model_validate(template.intent)
            engine = "local"
        elif decision_kind is not None:
            resolved_intent = parse_local(question)
            engine = "local"
        else:
            try:
                resolved_intent = (
                    resolver(question) if resolver is not None else parse_local(question)
                )
            except AppError as exc:
                if resolver is None or not exc.code.startswith("AI_"):
                    raise
                fallback_warning = query_fallback_warning(exc)
                try:
                    resolved_intent = parse_local(question)
                except AppError:
                    raise ai_fallback_unsupported_error(exc) from None
                engine = "local"
        intent = _validated_intent(resolved_intent)
        built = build_select(intent)
        raw_rows = _execute_business_select(session, built)
        context, rows = _extract_context(raw_rows)
        scenario = scenario_for_template_question(question) or SCENARIO_BY_ID["ecommerce"]
        rows, answer, summary = _answer(intent, rows, context, decision_kind, scenario)
        chart_type = "line" if (decision_kind or _answer_kind(intent)) in {"week_over_week", "forecast", "root_cause"} or set(
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
            provenance="local_fallback" if fallback_warning else engine,
            warning=fallback_warning,
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


def query_fallback_warning(error: Exception) -> ServiceWarning:
    return ai_service_warning(
        error,
        message="AI 服务不可用，已切换到本地规则解析。",
    )


def ai_fallback_unsupported_error(error: AppError) -> AppError:
    sanitized = query_fallback_warning(error)
    status_code = error.status_code if 400 <= error.status_code <= 599 else 502
    return AppError(
        code=sanitized.code,
        message=error.message,
        status_code=status_code,
        details={"local_fallback": "unsupported"},
    )


def _validated_intent(value: QueryIntent | dict[str, Any]) -> QueryIntent:
    payload = value.model_dump() if isinstance(value, QueryIntent) else value
    return QueryIntent.model_validate(payload)


def _execute_business_select(session: Session, built: BuiltQuery) -> list[dict[str, Any]]:
    timeout_ms = get_settings().query_timeout_seconds * 1000
    session.execute(
        text("SET SESSION MAX_EXECUTION_TIME = :timeout_ms"),
        {"timeout_ms": timeout_ms},
    )
    business_failed = False
    try:
        return [
            dict(row)
            for row in session.execute(text(built.sql), built.params).mappings()
        ]
    except BaseException:
        business_failed = True
        raise
    finally:
        try:
            session.execute(text("SET SESSION MAX_EXECUTION_TIME = DEFAULT"))
        except Exception:
            session.invalidate()
            if not business_failed:
                raise


def _extract_context(rows: list[dict[str, Any]]) -> tuple[DataContext, list[dict[str, Any]]]:
    if not rows or not any(int(row.get("_metric_authorized") or 0) > 0 for row in rows):
        raise MetricNotAvailableError()
    context = DataContext(
        data_start=rows[0].get("_data_start"),
        data_as_of=rows[0].get("_data_as_of"),
    )
    business_rows = [
        {
            key: value
            for key, value in row.items()
            if key
            not in {
                "_data_start",
                "_data_as_of",
                "_match_count",
                "_metric_authorized",
            }
        }
        for row in rows
        if int(row.get("_match_count") or 0) > 0
    ]
    return context, business_rows


def _answer(
    intent: QueryIntent,
    rows: list[dict[str, Any]],
    context: DataContext,
    decision_kind: str | None = None,
    scenario: ScenarioDefinition | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str]:
    scenario = scenario or SCENARIO_BY_ID["ecommerce"]
    answer_kind = decision_kind or _answer_kind(intent)
    if not rows:
        return [], _empty_answer(answer_kind, intent), _summary(intent, rows, context, scenario)
    if answer_kind == "week_over_week":
        answer, comparison_rows = _week_over_week(rows)
        return comparison_rows, answer, _week_summary(answer, context)
    if answer_kind == "forecast":
        answer, forecast_rows = _forecast_answer(rows)
        return forecast_rows, answer, _forecast_summary(answer, context, scenario)
    if answer_kind == "promotion_scenario":
        answer, scenario_rows = _scenario_answer(intent, rows)
        return scenario_rows, answer, _scenario_summary(answer, context, scenario)
    if answer_kind == "root_cause":
        answer = _root_cause_answer(rows, scenario)
        return rows, answer, _root_cause_summary(answer, context, scenario)
    if answer_kind == "recommendation":
        answer = _recommendation_answer(rows, scenario)
        return rows, answer, _recommendation_summary(answer, context, scenario)
    return rows, None, _summary(intent, rows, context, scenario)


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
    if answer_kind == "root_cause":
        return {"kind": "root_cause", "unavailable": True}
    if answer_kind == "recommendation":
        return {"kind": "recommendation", "unavailable": True}
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
    region = intent.filters.get("region", "全部区域")
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


def _root_cause_answer(
    rows: list[dict[str, Any]], scenario: ScenarioDefinition
) -> dict[str, Any]:
    chronological_rows = sorted(rows, key=lambda row: str(row["month"]))
    if len(chronological_rows) < 2:
        return {"kind": "root_cause", "unavailable": True}
    previous, current = chronological_rows[-2:]
    previous_value = Decimal(str(previous["metric_value"]))
    current_value = Decimal(str(current["metric_value"]))
    change = current_value - previous_value
    change_rate = change / previous_value if previous_value else None
    direction = "下降" if change < 0 else "增长" if change > 0 else "持平"
    return {
        "kind": "root_cause",
        "direction": direction,
        "current": current,
        "previous": previous,
        "absolute_change": change,
        "percent_change": change_rate,
        "checks": list(scenario.root_cause_checks),
    }


def _recommendation_answer(
    rows: list[dict[str, Any]], scenario: ScenarioDefinition
) -> dict[str, Any]:
    priority = rows[0]
    region = str(priority.get("region") or "当前区域")
    return {
        "kind": "recommendation",
        "region": region,
        "current_amount": Decimal(str(priority["metric_value"])),
        "actions": [item.format(region=region) for item in scenario.recommendation_actions],
        "guardrail": f"建议基于当前{scenario.amount_label}排序生成，不代表已确认的因果关系或经营承诺。",
    }


def _summary(
    intent: QueryIntent,
    rows: list[dict[str, Any]],
    context: DataContext,
    scenario: ScenarioDefinition,
) -> str:
    metric_label = {
        "amount": scenario.amount_label,
        "quantity": scenario.quantity_label,
    }.get(intent.metric, METRIC_LABELS[intent.metric])
    dimension_labels = {
        **DIMENSION_LABELS,
        "region": scenario.region_label,
        "product_name": scenario.entity_label,
        "category": scenario.category_label,
        "customer_type": scenario.customer_label,
    }
    prefix = _summary_prefix(context)
    if not rows:
        if context.data_as_of is None:
            return f"当前数据集为空；暂无可用订单数据，无法查询{metric_label}。"
        return f"{prefix}未查询到符合条件的{metric_label}数据。"
    joined_dimension_labels = "、".join(dimension_labels[item] for item in intent.dimensions)
    if intent.analysis_kind == "ranking" and intent.dimensions:
        first_dimension = intent.dimensions[0]
        leading_value = rows[0].get(first_dimension)
        leading_metric = rows[0].get("metric_value")
        return (
            f"{prefix}已返回{len(rows)}条{metric_label}数据，排名第一的"
            f"{dimension_labels[first_dimension]}为{leading_value}，{metric_label}为{leading_metric}。"
        )
    if joined_dimension_labels:
        return f"{prefix}已返回{len(rows)}条{metric_label}数据，按{joined_dimension_labels}汇总。"
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


def _forecast_summary(
    answer: dict[str, Any], context: DataContext, scenario: ScenarioDefinition
) -> str:
    prefix = _summary_prefix(context)
    prediction = answer["prediction"]
    if prediction is None:
        return f"{prefix}历史数据不足，无法生成下月{scenario.amount_label}预测。"
    return (
        f"{prefix}预计{prediction['month']}{scenario.amount_label}约为{prediction['amount']}。"
        f"{prediction['basis']}预测仅供经营分析参考。"
    )


def _scenario_summary(
    answer: dict[str, Any], context: DataContext, scenario: ScenarioDefinition
) -> str:
    assumptions = answer["assumptions"]
    return (
        f"{_summary_prefix(context)}这是演示情景估算，并非实际观测结果："
        f"假设{answer['region']}业务投入增加{assumptions['promotion_increase']:.0%}"
        f"（弹性{assumptions['promotion_elasticity']:.2f}），价格下降{assumptions['price_drop']:.0%}"
        f"（弹性{assumptions['price_elasticity']:.2f}），净影响为{answer['net_change']:.2%}，"
        f"模拟{scenario.amount_label}为{answer['simulated_amount']}。"
    )


def _root_cause_summary(
    answer: dict[str, Any], context: DataContext, scenario: ScenarioDefinition
) -> str:
    if answer.get("unavailable"):
        return f"{_summary_prefix(context)}可比月份不足，暂不能形成变化归因。"
    change_rate = answer["percent_change"]
    rate_text = "无法计算比例" if change_rate is None else f"{abs(change_rate):.2%}"
    return (
        f"{_summary_prefix(context)}{answer['current']['month']}{scenario.amount_label}为"
        f"{answer['current']['metric_value']}，较{answer['previous']['month']}"
        f"{answer['direction']}{rate_text}。这是数据确认的变化，"
        f"需要优先核查{scenario.entity_label}、{scenario.customer_label}和{scenario.region_label}执行明细。"
    )


def _recommendation_summary(
    answer: dict[str, Any], context: DataContext, scenario: ScenarioDefinition
) -> str:
    if answer.get("unavailable"):
        return f"{_summary_prefix(context)}暂无可用于生成行动建议的{scenario.region_label}{scenario.amount_label}。"
    return (
        f"{_summary_prefix(context)}当前优先关注{answer['region']}，"
        f"其最新月{scenario.amount_label}为{answer['current_amount']}。"
        "建议先完成明细核查，再以小范围动作验证改善效果。"
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
