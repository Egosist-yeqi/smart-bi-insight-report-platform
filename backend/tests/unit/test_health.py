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
