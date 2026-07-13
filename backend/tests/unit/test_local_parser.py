import pytest
from pydantic import ValidationError

from app.query.local_parser import UnrecognizedQuestionError, parse_local
from app.query.schemas import QueryIntent


@pytest.mark.parametrize(
    ("question", "metric", "dimensions", "time_range", "analysis_kind"),
    [
        (
            "上月华东区销售额最高的产品是什么？",
            "amount",
            ["product_name"],
            "latest_month",
            "ranking",
        ),
        (
            "本月各区域销售额排名如何？",
            "amount",
            ["region"],
            "latest_month",
            "ranking",
        ),
        (
            "最近30天销售额趋势如何？",
            "amount",
            ["week"],
            "last_30_days",
            "trend",
        ),
        (
            "哪个产品类别的毛利最高？",
            "profit",
            ["category"],
            "latest_month",
            "ranking",
        ),
        (
            "本周订单量相比上周下降了吗？",
            "order_count",
            ["week"],
            "last_30_days",
            "comparison",
        ),
        (
            "为什么本月华南区销售额出现下降？",
            "amount",
            ["month"],
            "last_30_days",
            "comparison",
        ),
        (
            "下个月销售额可能是多少？",
            "amount",
            ["month"],
            "all",
            "trend",
        ),
        (
            "如果华东区促销投入增加10%，价格下降5%，销售额会怎样？",
            "amount",
            ["region"],
            "latest_month",
            "detail",
        ),
    ],
)
def test_local_parser_supports_each_shipped_sample_question(
    question, metric, dimensions, time_range, analysis_kind
):
    intent = parse_local(question)

    assert intent.metric == metric
    assert intent.dimensions == dimensions
    assert intent.time_range == time_range
    assert intent.analysis_kind == analysis_kind


def test_local_parser_understands_top_product_in_east_china():
    intent = parse_local("上月华东区销售额最高的产品是什么？")

    assert intent.filters["region"] == "华东"
    assert intent.sort_direction == "desc"
    assert intent.limit == 1


def test_local_parser_rejects_unrecognized_questions():
    with pytest.raises(UnrecognizedQuestionError, match="无法识别"):
        parse_local("请执行所有数据库维护操作")


def test_query_intent_rejects_unknown_filter_and_limit_above_cap():
    with pytest.raises(ValidationError):
        QueryIntent(metric="amount", filters={"unknown": "value"})

    with pytest.raises(ValidationError):
        QueryIntent(metric="amount", limit=101)
