import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import AIProviderConfig
from app.db.seed import seed_database
from app.db.session import get_session
from app.main import create_app


@pytest.fixture(autouse=True)
def valid_fernet_key(monkeypatch):
    monkeypatch.setenv("APP_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _provider_payload(api_key: str = "test-key") -> dict:
    return {
        "provider_name": "Mock LLM",
        "base_url": "http://mock-llm:8090/v1",
        "api_key": api_key,
        "model": "mock-model",
        "timeout_seconds": 5,
        "enabled": True,
    }


def test_ai_settings_are_masked_and_drive_query(db_session):
    seed_database(db_session)
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        unsaved = api_client.post("/api/settings/ai/test", json=_provider_payload())
        assert unsaved.status_code == 200
        assert unsaved.json()["data"]["status"] == "connected"
        assert api_client.get("/api/settings/ai").json()["data"]["configured"] is False

        saved = api_client.put("/api/settings/ai", json=_provider_payload())
        saved_data = saved.json()["data"]
        stored = db_session.get(AIProviderConfig, 1)

        assert saved.status_code == 200
        assert saved_data["api_key_hint"] == "test...-key"
        assert "test-key" not in saved.text
        assert stored is not None
        assert stored.encrypted_api_key != "test-key"
        encrypted_api_key = stored.encrypted_api_key

        report = api_client.post(
            "/api/reports/generate",
            json={"report_type": "月报", "modules": ["overview"]},
        )
        assert report.status_code == 200
        assert report.json()["data"]["engine"] == "ai"
        assert "销售额" in report.json()["data"]["sections"][0]["content"]

        updated = api_client.put("/api/settings/ai", json=_provider_payload(api_key=""))
        assert updated.status_code == 200
        assert db_session.get(AIProviderConfig, 1).encrypted_api_key == encrypted_api_key

        tested = api_client.post("/api/settings/ai/test", json={})
        queried = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})

        assert tested.status_code == 200
        assert tested.json()["data"]["status"] == "connected"
        assert queried.status_code == 200
        assert queried.json()["data"]["engine"] == "ai"
        assert "test-key" not in queried.text
        assert "test-key" not in api_client.get("/api/query-history").text

        deleted = api_client.delete("/api/settings/ai")
        local_query = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})

        assert deleted.status_code == 200
        assert deleted.json()["data"] == {"configured": False, "ai_mode": "local"}
        assert local_query.status_code == 200
        assert local_query.json()["data"]["engine"] == "local"

    app.dependency_overrides.clear()


def test_query_falls_back_to_local_rules_when_ai_call_fails(db_session):
    seed_database(db_session)
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        payload = _provider_payload()
        payload["base_url"] = "http://mock-llm:8091/v1"
        saved = api_client.put("/api/settings/ai", json=payload)
        result = api_client.post(
            "/api/query", json={"question": "本月各区域销售额排名如何？"}
        )

        assert saved.status_code == 200
        assert result.status_code == 200
        assert result.json()["data"]["engine"] == "local"
        assert "已使用本地规则解析" in result.json()["data"]["summary"]

    app.dependency_overrides.clear()
