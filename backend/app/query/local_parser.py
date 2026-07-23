from app.core.errors import AppError
from app.query.schemas import QueryIntent
from app.scenarios.catalog import template_for_question


class UnrecognizedQuestionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="UNRECOGNIZED_QUESTION",
            message="无法识别该问题，请使用示例中的经营分析问法。",
            status_code=400,
        )


def decision_support_kind(question: str) -> str | None:
    normalized = question.strip()
    template = template_for_question(normalized)
    if template is not None:
        return template.decision_kind
    if any(keyword in normalized for keyword in ("如果", "假设", "促销", "价格")):
        return "promotion_scenario"
    if any(keyword in normalized for keyword in ("下个月", "预测", "预计")):
        return "forecast"
    if any(keyword in normalized for keyword in ("为什么", "原因", "归因")):
        return "root_cause"
    if any(keyword in normalized for keyword in ("怎么办", "措施", "建议", "优先关注", "下一步")):
        return "recommendation"
    return None


def parse_local(question: str) -> QueryIntent:
    normalized = question.strip()
    template = template_for_question(normalized)
    if template is not None:
        return QueryIntent.model_validate(template.intent)

    if decision_support_kind(normalized) == "promotion_scenario":
        filters = {"region": "华东"} if "华东" in normalized else {}
        return QueryIntent(
            metric="amount",
            dimensions=["region"],
            time_range="latest_month",
            filters=filters,
            analysis_kind="detail",
        )
    if decision_support_kind(normalized) == "forecast":
        return QueryIntent(
            metric="amount",
            dimensions=["month"],
            time_range="all",
            sort_direction="asc",
            analysis_kind="trend",
        )
    if decision_support_kind(normalized) == "root_cause":
        filters = {"region": "华南"} if "华南" in normalized else {}
        return QueryIntent(
            metric="amount",
            dimensions=["month"],
            time_range="all",
            filters=filters,
            sort_direction="asc",
            analysis_kind="comparison",
        )
    if decision_support_kind(normalized) == "recommendation":
        filters = {"region": "华南"} if "华南" in normalized else {}
        return QueryIntent(
            metric="amount",
            dimensions=["region"],
            time_range="latest_month",
            filters=filters,
            sort_direction="asc",
            analysis_kind="detail",
        )

    if "华东" in normalized and "最高" in normalized and "产品" in normalized:
        return QueryIntent(
            metric="amount",
            dimensions=["product_name"],
            time_range="latest_month",
            filters={"region": "华东"},
            limit=1,
        )
    if "各区域" in normalized or ("区域" in normalized and "排名" in normalized):
        return QueryIntent(metric="amount", dimensions=["region"], time_range="latest_month")
    if "最近30天" in normalized or "最近 30 天" in normalized:
        return QueryIntent(
            metric="amount",
            dimensions=["week"],
            time_range="last_30_days",
            sort_direction="asc",
            analysis_kind="trend",
        )
    if "毛利" in normalized or "利润" in normalized:
        return QueryIntent(metric="profit", dimensions=["category"], time_range="latest_month")
    if "本周" in normalized and "上周" in normalized and "订单量" in normalized:
        return QueryIntent(
            metric="order_count",
            aggregation="count",
            dimensions=["week"],
            time_range="last_30_days",
            sort_direction="desc",
            limit=2,
            analysis_kind="comparison",
        )
    raise UnrecognizedQuestionError()
