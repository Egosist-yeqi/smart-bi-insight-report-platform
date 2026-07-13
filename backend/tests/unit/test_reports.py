import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db.models import Base
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


def test_report_keeps_data_derived_content_when_narrative_callback_fails(db_session):
    seed_database(db_session)

    result = generate_report(
        db_session,
        ReportRequest(report_type="自定义报告", modules=["overview"]),
        narrative=lambda _section: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )

    assert result.engine == "ai"
    assert "销售概览" in result.markdown
    assert "unavailable" not in result.markdown
