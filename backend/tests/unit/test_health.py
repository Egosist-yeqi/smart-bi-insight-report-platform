from fastapi.testclient import TestClient


def test_health_reports_app_and_database(monkeypatch):
    from app.core.config import get_settings
    from app.db.session import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

    try:
        from app.main import create_app

        monkeypatch.setattr("app.api.health.database_status", lambda: "up")
        monkeypatch.setattr("app.api.health.seeded_order_count", lambda: 0)
        with TestClient(create_app()) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "app": "up",
            "database": "up",
            "seeded_orders": 0,
            "ai_mode": "local",
        }
        assert response.json()["request_id"]
        assert get_engine.cache_info().currsize == 0
    finally:
        get_engine.cache_clear()
        get_settings.cache_clear()


def test_health_returns_service_unavailable_envelope_when_database_is_down(
    monkeypatch,
):
    from app.main import create_app

    count_calls = 0

    def record_count_call():
        nonlocal count_calls
        count_calls += 1
        return 0

    monkeypatch.setattr("app.api.health.database_status", lambda: "down")
    monkeypatch.setattr("app.api.health.seeded_order_count", record_count_call)

    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "health-test-id"})

    assert response.status_code == 503
    assert count_calls == 0
    assert response.headers["X-Request-ID"] == "health-test-id"
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "数据库连接不可用。",
            "details": {
                "app": "up",
                "database": "down",
                "seeded_orders": 0,
                "ai_mode": "local",
            },
        },
        "request_id": "health-test-id",
    }
