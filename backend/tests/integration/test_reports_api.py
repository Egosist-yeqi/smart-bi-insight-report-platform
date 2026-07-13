from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import QueryHistory, SalesOrder
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app


@pytest.fixture()
def api_client(db_session):
    seed_database(db_session)
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_report_and_history_endpoints(api_client, db_session):
    report = api_client.post(
        "/api/reports/generate",
        json={"report_type": "月报", "modules": ["overview", "region"]},
    )
    api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})
    history = api_client.get("/api/query-history")

    assert report.status_code == 200
    report_data = report.json()["data"]
    assert [section["id"] for section in report_data["sections"]] == [
        "overview",
        "region",
    ]
    assert report_data["engine"] == "local"
    latest_order = db_session.scalar(
        select(SalesOrder.order_date).order_by(SalesOrder.order_date.desc()).limit(1)
    )
    assert latest_order is not None
    expected_period = f"{date(latest_order.year, latest_order.month, 1).isoformat()}/{latest_order.isoformat()}"
    assert report_data["period"] == expected_period
    assert report_data["title"].startswith(expected_period)
    assert report_data["generated_at"] in report_data["markdown"]
    assert history.status_code == 200
    assert history.json()["data"][0]["question"]
    assert "api_key" not in history.text.lower()
    assert "generated_sql" not in history.text.lower()
    assert "parameters_json" not in history.text.lower()


def test_query_history_is_newest_first_and_has_a_bounded_page(api_client, db_session):
    newest = datetime(2026, 7, 1, 9, 30)
    oldest = newest - timedelta(minutes=1)
    db_session.add_all(
        [
            QueryHistory(
                question="较早的问题",
                engine="local",
                status="succeeded",
                duration_ms=1,
                created_at=oldest,
            ),
            QueryHistory(
                question="最新的问题",
                engine="local",
                status="failed",
                error_code="UNRECOGNIZED_QUESTION",
                duration_ms=2,
                created_at=newest,
            ),
        ]
    )
    db_session.commit()

    response = api_client.get("/api/query-history?limit=1&offset=0")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "id": db_session.scalar(
                select(QueryHistory.id).where(QueryHistory.question == "最新的问题")
            ),
            "question": "最新的问题",
            "engine": "local",
            "summary": None,
            "status": "failed",
            "error_code": "UNRECOGNIZED_QUESTION",
            "duration_ms": 2,
            "created_at": newest.isoformat(),
        }
    ]


def test_report_rejects_an_empty_module_list(api_client):
    response = api_client.post(
        "/api/reports/generate",
        json={"report_type": "月报", "modules": []},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REPORT_MODULES_REQUIRED"
