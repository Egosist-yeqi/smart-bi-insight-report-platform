from app.core.errors import AppError
from app.query.schemas import QueryIntent


class UnrecognizedQuestionError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="UNRECOGNIZED_QUESTION",
            message="无法识别该问题，请使用示例中的经营分析问法。",
            status_code=400,
        )


def parse_local(question: str) -> QueryIntent:
    normalized = question.strip()

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
    if "为什么" in normalized or "原因" in normalized or "归因" in normalized:
        filters = {"region": "华南"} if "华南" in normalized else {}
        return QueryIntent(
            metric="amount",
            dimensions=["month"],
            time_range="last_30_days",
            filters=filters,
            sort_direction="asc",
            analysis_kind="comparison",
        )
    if "下个月" in normalized or "预测" in normalized or "预计" in normalized:
        return QueryIntent(
            metric="amount",
            dimensions=["month"],
            time_range="all",
            sort_direction="asc",
            analysis_kind="trend",
        )
    if "如果" in normalized or "假设" in normalized or "促销" in normalized:
        filters = {"region": "华东"} if "华东" in normalized else {}
        return QueryIntent(
            metric="amount",
            dimensions=["region"],
            time_range="latest_month",
            filters=filters,
            analysis_kind="detail",
        )

    raise UnrecognizedQuestionError()
