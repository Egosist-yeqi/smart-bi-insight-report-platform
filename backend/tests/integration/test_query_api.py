import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.db.models import MetricDefinition, QueryHistory, SalesOrder
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
    assert data["provenance"] == "local"
    assert data["warning"] is None
    assert data["safe"] is True
    assert data["rows"][0]["product_name"]
    assert data["sql"].startswith("SELECT")
    assert data["summary"]
    assert data["chart_type"] == "bar"


@pytest.mark.parametrize(
    "question",
    [
        "上月华东区销售额最高的产品是什么？",
        "本月各区域销售额排名如何？",
        "最近30天销售额趋势如何？",
        "哪个产品类别的毛利最高？",
        "本周订单量相比上周下降了吗？",
        "为什么本月华南区销售额出现下降？",
        "下个月销售额可能是多少？",
        "如果华东区促销投入增加10%，价格下降5%，销售额会怎样？",
    ],
)
def test_all_shipped_sample_questions_execute_against_registered_metrics(
    api_client, question
):
    response = api_client.post("/api/query", json={"question": question})

    assert response.status_code == 200
    assert response.json()["data"]["safe"] is True


@pytest.mark.parametrize("registry_change", ["disable", "delete"])
def test_query_api_rejects_an_unavailable_registered_metric_in_one_select(
    api_client, db_session, monkeypatch, registry_change
):
    metric = db_session.scalar(
        select(MetricDefinition).where(MetricDefinition.metric_code == "sales_amount")
    )
    assert metric is not None
    if registry_change == "disable":
        metric.enabled = False
    else:
        db_session.delete(metric)
    db_session.commit()

    original_execute = db_session.execute
    business_selects = []

    def recording_execute(statement, *args, **kwargs):
        sql = str(statement).strip()
        if sql.upper().startswith("SELECT") and "FROM (SELECT MIN(order_date)" in sql:
            business_selects.append((sql, args[0] if args else kwargs.get("params", {})))
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", recording_execute)
    response = api_client.post(
        "/api/query",
        json={"question": "上月华东区销售额最高的产品是什么？"},
    )
    monkeypatch.setattr(db_session, "execute", original_execute)

    history = db_session.scalar(
        select(QueryHistory).order_by(QueryHistory.id.desc()).limit(1)
    )
    body = response.json()
    assert response.status_code == 400
    assert body["error"]["code"] == "METRIC_NOT_AVAILABLE"
    assert body["error"]["message"] == "该指标未登记或已停用，无法执行查询。"
    assert "data" not in body
    assert len(business_selects) == 1
    assert business_selects[0][1]["metric_code"] == "sales_amount"
    assert history is not None
    assert history.status == "failed"
    assert history.error_code == "METRIC_NOT_AVAILABLE"


def test_query_service_rejects_unseeded_quantity_metric_and_records_failure(db_session):
    seed_database(db_session)

    with pytest.raises(AppError) as error:
        run_query(
            db_session,
            "查询销售数量",
            resolver=lambda _question: QueryIntent(metric="quantity"),
        )

    history = db_session.scalar(
        select(QueryHistory).order_by(QueryHistory.id.desc()).limit(1)
    )
    assert error.value.code == "METRIC_NOT_AVAILABLE"
    assert history is not None
    assert history.status == "failed"
    assert history.error_code == "METRIC_NOT_AVAILABLE"


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


@pytest.mark.parametrize(
    "question",
    [
        "上月华东区销售额最高的产品是什么？",
        "下个月销售额可能是多少？",
    ],
)
def test_query_service_scopes_timeout_around_exactly_one_business_select(
    db_session, monkeypatch, question
):
    seed_database(db_session)
    original_execute = db_session.execute
    statements = []

    def recording_execute(statement, *args, **kwargs):
        statements.append(str(statement).strip())
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", recording_execute)

    run_query(db_session, question)

    select_statements = [
        statement for statement in statements if statement.upper().startswith("SELECT")
    ]
    timeout_index = next(
        index
        for index, statement in enumerate(statements)
        if statement.upper().startswith("SET SESSION MAX_EXECUTION_TIME")
    )
    select_index = statements.index(select_statements[0])
    restore_index = next(
        index
        for index, statement in enumerate(statements)
        if statement.upper() == "SET SESSION MAX_EXECUTION_TIME = DEFAULT"
    )

    assert len(select_statements) == 1
    assert timeout_index < select_index < restore_index


def test_query_service_restores_timeout_after_the_business_select_fails(
    db_session, monkeypatch
):
    seed_database(db_session)
    original_execute = db_session.execute
    statements = []

    def failing_business_select(statement, *args, **kwargs):
        sql = str(statement).strip()
        statements.append(sql)
        if sql.upper().startswith("SELECT"):
            raise RuntimeError("synthetic query failure")
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", failing_business_select)

    with pytest.raises(AppError) as error:
        run_query(db_session, "本月各区域销售额排名如何？")

    assert getattr(error.value, "code", None) == "QUERY_EXECUTION_FAILED"
    assert [
        "SELECT" if statement.upper().startswith("SELECT") else statement.upper()
        for statement in statements
    ][:3] == [
        "SET SESSION MAX_EXECUTION_TIME = :TIMEOUT_MS",
        "SELECT",
        "SET SESSION MAX_EXECUTION_TIME = DEFAULT",
    ]
    assert sum(statement.upper().startswith("SELECT") for statement in statements) == 1


def test_query_service_invalidates_connection_when_timeout_restore_fails(
    db_session, monkeypatch
):
    seed_database(db_session)
    original_execute = db_session.execute
    original_invalidate = db_session.invalidate
    invalidated = False

    def fail_restore(statement, *args, **kwargs):
        if str(statement).strip().upper() == "SET SESSION MAX_EXECUTION_TIME = DEFAULT":
            raise RuntimeError("synthetic restore failure")
        return original_execute(statement, *args, **kwargs)

    def record_invalidation():
        nonlocal invalidated
        invalidated = True
        return original_invalidate()

    monkeypatch.setattr(db_session, "execute", fail_restore)
    monkeypatch.setattr(db_session, "invalidate", record_invalidation)

    with pytest.raises(AppError) as error:
        run_query(db_session, "本月各区域销售额排名如何？")

    assert error.value.code == "QUERY_EXECUTION_FAILED"
    assert invalidated is True


def test_query_service_preserves_context_for_a_dimensioned_zero_match(db_session, monkeypatch):
    seed_database(db_session)
    expected_start = db_session.scalar(select(func.min(SalesOrder.order_date)))
    expected_as_of = db_session.scalar(select(func.max(SalesOrder.order_date)))
    original_execute = db_session.execute
    statements = []

    def recording_execute(statement, *args, **kwargs):
        statements.append(str(statement).strip())
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", recording_execute)

    result = run_query(
        db_session,
        "查询不存在区域",
        resolver=lambda _question: QueryIntent(
            metric="amount",
            dimensions=["region"],
            filters={"region": "不存在区域"},
            time_range="latest_month",
            analysis_kind="ranking",
        ),
    )

    select_statements = [
        statement for statement in statements if statement.upper().startswith("SELECT")
    ]
    timeout_index = next(
        index
        for index, statement in enumerate(statements)
        if statement.upper().startswith("SET SESSION MAX_EXECUTION_TIME")
    )
    restore_index = next(
        index
        for index, statement in enumerate(statements)
        if statement.upper() == "SET SESSION MAX_EXECUTION_TIME = DEFAULT"
    )

    assert len(select_statements) == 1
    assert timeout_index < statements.index(select_statements[0]) < restore_index
    assert result.data_as_of == expected_as_of
    assert result.data_period == f"数据范围{expected_start.isoformat()}至{expected_as_of.isoformat()}"
    assert result.query_period == f"{expected_as_of:%Y-%m}"
    assert result.rows == []
    assert "未查询到符合条件" in result.summary


def test_query_service_reports_a_truly_empty_dataset_for_dimensionless_aggregate(db_session):
    seed_database(db_session)
    db_session.execute(delete(SalesOrder))
    db_session.commit()

    result = run_query(
        db_session,
        "查询空数据集",
        resolver=lambda _question: QueryIntent(metric="amount", time_range="all"),
    )

    assert result.data_as_of is None
    assert result.data_period == "暂无可用数据"
    assert result.query_period == "暂无可用数据"
    assert result.rows == []
    assert result.answer is None
    assert "当前数据集为空" in result.summary
    assert "未查询到符合条件" not in result.summary
