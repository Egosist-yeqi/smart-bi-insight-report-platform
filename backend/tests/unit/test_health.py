from fastapi.testclient import TestClient


def test_health_reports_app_and_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://test:test@mysql/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-encryption-key")

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        from app.main import create_app

        monkeypatch.setattr("app.api.health.database_status", lambda: "up")
        client = TestClient(create_app())

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["data"] == {
            "app": "up",
            "database": "up",
            "seeded_orders": 0,
            "ai_mode": "local",
        }
        assert response.json()["request_id"]
    finally:
        get_settings.cache_clear()
