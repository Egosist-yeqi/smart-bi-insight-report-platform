from fastapi.testclient import TestClient


def test_health_reports_app_and_database(monkeypatch):
    from app.core.config import get_settings
    from app.db.session import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

    try:
        from app.main import create_app

        monkeypatch.setattr(
            "app.api.health.health_snapshot",
            lambda: {
                "app": "up",
                "database": "up",
                "seeded_orders": 0,
                "ai_mode": "local",
                "provider": None,
            },
        )
        with TestClient(create_app()) as client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "app": "up",
            "database": "up",
            "seeded_orders": 0,
            "ai_mode": "local",
            "provider": None,
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

    snapshot_calls = 0

    def database_down_snapshot():
        nonlocal snapshot_calls
        snapshot_calls += 1
        return {
            "app": "up",
            "database": "down",
            "seeded_orders": 0,
            "ai_mode": "local",
            "provider": None,
        }

    monkeypatch.setattr("app.api.health.health_snapshot", database_down_snapshot)

    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"X-Request-ID": "health-test-id"})

    assert response.status_code == 503
    assert snapshot_calls == 1
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
                "provider": None,
            },
        },
        "request_id": "health-test-id",
    }
