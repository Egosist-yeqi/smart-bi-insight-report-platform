import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import QueryHistory
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


def test_query_api_runs_local_intent_against_mysql(api_client):
    response = api_client.post(
        "/api/query",
        json={"question": "上月华东区销售额最高的产品是什么？"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["engine"] == "local"
    assert data["safe"] is True
    assert data["rows"][0]["product_name"]
    assert data["sql"].startswith("SELECT")
    assert data["summary"]
    assert data["chart_type"] == "bar"


def test_query_api_records_a_failed_unrecognized_question(api_client, db_session):
    response = api_client.post("/api/query", json={"question": "请删除销售订单"})

    history = db_session.scalar(select(QueryHistory))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNRECOGNIZED_QUESTION"
    assert history is not None
    assert history.status == "failed"
    assert history.error_code == "UNRECOGNIZED_QUESTION"
