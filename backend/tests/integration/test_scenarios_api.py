from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import QueryHistory, SalesOrder, ScenarioState
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app


def _client(db_session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    return app, TestClient(app)


def test_scenario_library_switches_to_a_complete_hospital_demo_dataset(db_session):
    seed_database(db_session)
    app, client = _client(db_session)
    with client:
        library = client.get("/api/scenarios")
        activated = client.post("/api/scenarios/hospital/activate")

    assert library.status_code == 200
    assert [item["id"] for item in library.json()["data"]["scenarios"]] == [
        "ecommerce", "hospital", "banking", "manufacturing", "internet"
    ]
    assert activated.status_code == 200
    assert activated.json()["data"]["orders_loaded"] == 540
    assert db_session.scalar(select(func.count()).select_from(SalesOrder)) == 540
    assert db_session.scalar(select(ScenarioState.scenario_id)) == "hospital"
    assert db_session.scalar(select(ScenarioState.data_source)) == "demo"
    assert "专家门诊" in set(db_session.scalars(select(SalesOrder.product_name)))
    app.dependency_overrides.clear()


def test_scenario_csv_import_replaces_active_dataset_and_validates_template(db_session):
    seed_database(db_session)
    app, client = _client(db_session)
    valid_csv = "\n".join(
        [
            "record_id,date,region,province,item_id,item_name,category,customer_type,quantity,amount,profit",
            "own-001,2026-06-01,华东分行,上海,101,企业结算服务,交易银行,企业客户,12,36000.00,18000.00",
        ]
    )
    with client:
        invalid = client.post(
            "/api/scenarios/import",
            json={"scenario_id": "banking", "csv_text": "date,amount\n2026-06-01,1"},
        )
        imported = client.post(
            "/api/scenarios/import",
            json={"scenario_id": "banking", "csv_text": valid_csv},
        )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "SCENARIO_IMPORT_INVALID"
    assert imported.status_code == 200
    assert imported.json()["data"]["rows_imported"] == 1
    order = db_session.scalar(select(SalesOrder))
    assert order is not None
    assert order.external_order_id == "IMPORT-banking-own-001"
    assert db_session.scalar(select(func.count()).select_from(QueryHistory)) == 0
    assert db_session.scalar(select(ScenarioState.scenario_id)) == "banking"
    assert db_session.scalar(select(ScenarioState.data_source)) == "imported"
    app.dependency_overrides.clear()


def test_scenario_csv_preview_validates_analysis_coverage_without_mutating_data(db_session):
    seed_database(db_session)
    app, client = _client(db_session)
    valid_csv = "\n".join(
        [
            "record_id,date,region,province,item_id,item_name,category,customer_type,quantity,amount,profit",
            "own-001,2026-01-01,华东分行,上海,101,企业结算服务,交易银行,企业客户,12,36000.00,18000.00",
            "own-002,2026-02-01,华南分行,广州,102,财富管理组合,财富管理,高净值客户,8,24000.00,9000.00",
            "own-003,2026-03-01,华东分行,上海,101,企业结算服务,交易银行,企业客户,10,30000.00,15000.00",
        ]
    )
    baseline_count = db_session.scalar(select(func.count()).select_from(SalesOrder))
    with client:
        preview = client.post(
            "/api/scenarios/import/preview",
            json={"scenario_id": "banking", "csv_text": valid_csv},
        )

    assert preview.status_code == 200
    data = preview.json()["data"]
    assert data["scenario"] == {"id": "banking", "title": "银行经营"}
    assert data["rows_valid"] == 3
    assert data["date_range"] == {"start": "2026-01-01", "end": "2026-03-01", "months": 3}
    assert data["dimensions"] == {"regions": 2, "categories": 2, "customer_types": 2}
    assert data["metrics"] == {"amount": 90000.0, "profit": 42000.0}
    assert db_session.scalar(select(func.count()).select_from(SalesOrder)) == baseline_count
    assert db_session.scalar(select(func.count()).select_from(QueryHistory)) == 0
    assert db_session.get(ScenarioState, 1) is None
    app.dependency_overrides.clear()


def test_every_industry_template_question_is_executable_without_ai_guessing(db_session):
    seed_database(db_session)
    app, client = _client(db_session)
    with client:
        library = client.get("/api/scenarios").json()["data"]["scenarios"]
        for scenario in library:
            activated = client.post(f"/api/scenarios/{scenario['id']}/activate")
            assert activated.status_code == 200
            for group in scenario["question_groups"]:
                for question in group["questions"]:
                    response = client.post("/api/query", json={"question": question})
                    data = response.json().get("data", {})
                    assert response.status_code == 200, question
                    assert data["engine"] == "local", question
                    assert data["rows"], question
    app.dependency_overrides.clear()
