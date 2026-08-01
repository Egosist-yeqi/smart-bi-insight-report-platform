from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

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


def test_dashboard_returns_filterable_mysql_aggregates(api_client):
    response = api_client.get("/api/dashboard", params={"region": "华东"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["kpis"]) == {"amount", "quantity", "avg_order_value", "profit_rate"}
    assert data["filters"]["region"] == "华东"
    assert data["regions"]
    assert data["products"]
    assert all(
        {"amount", "profit", "profit_rate"}.issubset(product)
        and Decimal(product["profit_rate"]) >= 0
        for product in data["products"]
    )
    assert len(data["trend"]) == 18


def test_metadata_returns_metrics_and_distinct_filter_values(api_client):
    response = api_client.get("/api/metadata")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["metrics"]) == 5
    assert set(data["regions"]) == {"华东", "华南", "华北", "西南", "华中"}
    assert set(data["categories"]) == {
        "工业传感",
        "数据服务",
        "智能硬件",
        "软件订阅",
        "边缘计算",
    }
    assert set(data["customer_types"]) == {"企业客户", "政府客户", "渠道客户"}
    assert data["data_scope"] == {
        "records": 540,
        "start_date": "2025-01-04",
        "end_date": "2026-06-27",
        "months": 18,
    }
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_anomaly_and_forecast_have_explainable_results(api_client):
    anomalies = api_client.get("/api/anomalies").json()["data"]
    forecast = api_client.get("/api/forecast").json()["data"]

    assert isinstance(anomalies["items"], list)
    assert all("evidence" in item for item in anomalies["items"])
    assert forecast["history"]
    assert forecast["prediction"]["is_estimate"] is True
    assert forecast["prediction"]["basis"]
