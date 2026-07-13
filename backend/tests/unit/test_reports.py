from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db.models import Base, SalesOrder
from app.db.seed import seed_database
from app.db.session import get_engine
from app.reports.schemas import ReportRequest
from app.reports.service import generate_report


@pytest.fixture()
def db_session():
    command.upgrade(Config("alembic.ini"), "head")
    engine = get_engine()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        get_engine.cache_clear()


def test_report_contains_only_selected_sections(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="月报", modules=["overview", "region", "forecast"]),
    )

    assert [section.id for section in result.sections] == [
        "overview",
        "region",
        "forecast",
    ]
    assert "销售概览" in result.markdown
    assert "区域分析" in result.markdown
    assert "趋势预测" in result.markdown
    assert "异常指标" not in result.markdown


def test_report_uses_canonical_order_for_selected_modules(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="周报", modules=["forecast", "overview", "region"]),
    )

    assert [section.id for section in result.sections] == [
        "overview",
        "region",
        "forecast",
    ]


def test_report_stays_local_when_every_narrative_callback_fails(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="自定义报告", modules=["overview"]),
        narrative=lambda _section: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )

    assert result.engine == "local"
    assert "销售概览" in result.markdown
    assert "unavailable" not in result.markdown
    assert "部分或全部章节附加了 AI 叙述" not in result.markdown


def test_report_marks_partial_successful_narrative_as_ai_assisted(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="月报", modules=["overview", "region"]),
        narrative=lambda section: "AI 补充结论" if section.id == "overview" else None,
    )

    assert result.engine == "ai"
    assert "AI 补充结论" in result.sections[0].content
    assert "AI 补充结论" not in result.sections[1].content
    assert "部分或全部章节附加了 AI 叙述" in result.markdown


def test_report_marks_successful_narrative_as_ai_assisted(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="月报", modules=["overview"]),
        narrative=lambda _section: "AI 补充结论",
    )

    assert result.engine == "ai"
    assert "AI 补充结论" in result.markdown
    assert "部分或全部章节附加了 AI 叙述" in result.markdown


def test_report_period_policy_uses_the_same_data_slice_for_all_period_sections(
    db_session,
):
    db_session.add_all(
        [
            _order("PERIOD-OLD", date(2025, 2, 1), Decimal("5000"), "历史区域", "历史产品"),
            _order("PERIOD-WEEK-ONE", date(2025, 3, 4), Decimal("20"), "周初区域", "周初产品"),
            _order("PERIOD-WEEK-TWO", date(2025, 3, 10), Decimal("50"), "最新区域", "最新产品"),
        ]
    )
    db_session.commit()

    weekly = generate_report(
        db_session,
        ReportRequest(report_type="周报", modules=["overview", "region", "ranking"]),
    )
    monthly = generate_report(
        db_session,
        ReportRequest(report_type="月报", modules=["overview", "region", "ranking"]),
    )
    custom = generate_report(
        db_session,
        ReportRequest(report_type="自定义报告", modules=["overview", "region", "ranking"]),
    )

    assert weekly.period == "2025-03-04/2025-03-10"
    assert weekly.title.startswith("2025-03-04/2025-03-10")
    assert "70.00元" in weekly.sections[0].content
    assert "最新区域" in weekly.sections[1].content
    assert "最新产品" in weekly.sections[2].content
    assert "历史区域" not in weekly.markdown
    assert monthly.period == "2025-03-01/2025-03-10"
    assert "70.00元" in monthly.sections[0].content
    assert custom.period == "2025-02-01/2025-03-10"
    assert "5,070.00元" in custom.sections[0].content
    assert "历史区域" in custom.sections[1].content
    assert "历史产品" in custom.sections[2].content


def test_report_escapes_database_and_narrative_markdown_injection(db_session):
    db_session.add(
        _order(
            "MARKDOWN-SAFETY",
            date(2025, 3, 10),
            Decimal("100"),
            "区域\n## 伪造标题\n|x|",
            "[伪造链接](https://example.test) <b>伪造 HTML</b>",
        )
    )
    db_session.commit()

    result = generate_report(
        db_session,
        ReportRequest(report_type="自定义报告", modules=["region", "ranking"]),
        narrative=lambda _section: (
            "第一段\n## 伪造叙述标题\n[伪造叙述链接](https://example.test) <script>bad</script>"
            "\n\n第二段 | 伪造表格 |"
        ),
    )

    assert "## 伪造标题" not in result.markdown
    assert "## 伪造叙述标题" not in result.markdown
    assert "[伪造链接](https://example.test)" not in result.markdown
    assert "[伪造叙述链接](https://example.test)" not in result.markdown
    assert "<b>伪造 HTML</b>" not in result.markdown
    assert "<script>bad</script>" not in result.markdown
    assert "\\#\\# 伪造标题" in result.markdown
    assert "\\[伪造链接\\]\\(https://example\\.test\\)" in result.markdown
    assert "&lt;script&gt;bad&lt;/script&gt;" in result.markdown
    assert "第一段" in result.markdown
    assert "第二段" in result.markdown


def _order(
    external_order_id: str,
    order_date: date,
    amount: Decimal,
    region: str,
    product_name: str,
) -> SalesOrder:
    return SalesOrder(
        external_order_id=external_order_id,
        order_date=order_date,
        region=region,
        province="测试省",
        product_id=1,
        product_name=product_name,
        category="测试分类",
        customer_type="测试客户",
        quantity=1,
        amount=amount,
        profit=amount / Decimal("10"),
    )
