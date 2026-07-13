import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import QueryHistory, SalesOrder
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app
from app.query.schemas import QueryIntent
from app.query.service import InvalidQueryIntentError, run_query


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


def test_query_api_uses_max_order_date_as_its_data_as_of_policy(api_client, db_session):
    expected_as_of = db_session.scalar(select(func.max(SalesOrder.order_date)))

    response = api_client.post(
        "/api/query",
        json={"question": "上月华东区销售额最高的产品是什么？"},
    )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["data_as_of"] == expected_as_of.isoformat()
    assert expected_as_of.isoformat() in data["summary"]
    assert "2026-06" in data["query_period"]
    assert data["rows"]


def test_query_api_answers_week_over_week_decline_with_a_comparison(api_client):
    response = api_client.post(
        "/api/query",
        json={"question": "本周订单量相比上周下降了吗？"},
    )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["chart_type"] == "line"
    assert data["answer"]["kind"] == "week_over_week"
    assert data["answer"]["current"]["week"]
    assert data["answer"]["previous"]["week"]
    assert data["answer"]["current"]["week"] > data["answer"]["previous"]["week"]
    assert data["answer"]["direction"] in {"decrease", "increase", "unchanged"}
    assert "较上一可用周" in data["summary"]


def test_query_api_answers_next_month_with_a_deterministic_forecast(api_client):
    response = api_client.post(
        "/api/query",
        json={"question": "下个月销售额可能是多少？"},
    )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["chart_type"] == "line"
    assert data["answer"]["kind"] == "forecast"
    assert data["answer"]["prediction"]["is_estimate"] is True
    assert data["answer"]["prediction"]["basis"]
    assert "预计" in data["summary"]


def test_query_api_answers_promotion_question_as_an_explicit_scenario(api_client):
    response = api_client.post(
        "/api/query",
        json={"question": "如果华东区促销投入增加10%，价格下降5%，销售额会怎样？"},
    )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["chart_type"] == "bar"
    assert data["answer"]["kind"] == "promotion_scenario"
    assert data["answer"]["is_estimate"] is True
    assert data["answer"]["assumptions"] == {
        "promotion_increase": 0.1,
        "promotion_elasticity": 0.42,
        "price_drop": 0.05,
        "price_elasticity": 0.68,
    }
    assert "演示情景" in data["summary"]


@pytest.mark.parametrize(
    "unsafe_intent",
    [
        QueryIntent.model_construct(metric="amount", aggregation="sum", limit=1_000_000),
        QueryIntent.model_construct(
            metric="amount", aggregation="sum", filters={"unknown": "value"}
        ),
    ],
)
def test_query_service_revalidates_model_construct_resolver_intents(
    db_session, monkeypatch, unsafe_intent
):
    import app.query.service as query_service

    seed_database(db_session)
    monkeypatch.setattr(
        query_service,
        "build_select",
        lambda _intent, **_kwargs: pytest.fail("build_select received an unsafe intent"),
    )

    with pytest.raises(InvalidQueryIntentError):
        run_query(db_session, "忽略问题", resolver=lambda _question: unsafe_intent)

    history = db_session.scalar(select(QueryHistory))
    assert history is not None
    assert history.status == "failed"
    assert history.error_code == "INVALID_QUERY_INTENT"


def test_query_service_revalidates_a_mutated_resolver_intent(db_session, monkeypatch):
    import app.query.service as query_service

    seed_database(db_session)
    unsafe_intent = QueryIntent(metric="amount")
    object.__setattr__(unsafe_intent, "limit", 1_000_000)
    monkeypatch.setattr(
        query_service,
        "build_select",
        lambda _intent, **_kwargs: pytest.fail("build_select received a mutated unsafe intent"),
    )

    with pytest.raises(InvalidQueryIntentError):
        run_query(db_session, "忽略问题", resolver=lambda _question: unsafe_intent)

    history = db_session.scalar(select(QueryHistory))
    assert history is not None
    assert history.status == "failed"
    assert history.error_code == "INVALID_QUERY_INTENT"
