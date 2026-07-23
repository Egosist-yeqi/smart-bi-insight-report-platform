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


def _provider_payload(api_key: str = "test-key", **overrides) -> dict:
    payload = {
        "provider_name": "Mock LLM",
        "base_url": "http://mock-llm:8090/v1",
        "api_key": api_key,
        "model": "mock-model",
        "timeout_seconds": 5,
        "enabled": True,
        "allow_private_network": True,
    }
    payload.update(overrides)
    return payload


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
        assert saved_data["api_key_hint"] == "te...ey"
        assert saved_data["allow_private_network"] is True
        assert "test-key" not in saved.text
        assert stored is not None
        assert stored.encrypted_api_key != "test-key"
        assert stored.allow_private_network is True
        encrypted_api_key = stored.encrypted_api_key

        report = api_client.post(
            "/api/reports/generate",
            json={"report_type": "月报", "modules": ["overview"]},
        )
        assert report.status_code == 200
        report_data = report.json()["data"]
        assert report_data["engine"] == "ai"
        assert report_data["provenance"] == "ai_assisted"
        assert report_data["warning"] is None
        assert "销售额" in report_data["sections"][0]["content"]

        updated = api_client.put("/api/settings/ai", json=_provider_payload(api_key=""))
        assert updated.status_code == 200
        assert db_session.get(AIProviderConfig, 1).encrypted_api_key == encrypted_api_key

        tested = api_client.post(
            "/api/settings/ai/test", json=_provider_payload(api_key="")
        )
        queried = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})

        assert tested.status_code == 200
        assert tested.json()["data"]["status"] == "connected"
        assert queried.status_code == 200
        assert queried.json()["data"]["engine"] == "ai"
        assert queried.json()["data"]["provenance"] == "ai"
        assert queried.json()["data"]["warning"] is None
        assert "test-key" not in queried.text
        assert "test-key" not in api_client.get("/api/query-history").text

        deleted = api_client.delete("/api/settings/ai")
        local_query = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})

        assert deleted.status_code == 200
        assert deleted.json()["data"] == {"configured": False, "ai_mode": "local"}
        assert local_query.status_code == 200
        assert local_query.json()["data"]["engine"] == "local"
        assert local_query.json()["data"]["provenance"] == "local"
        assert local_query.json()["data"]["warning"] is None

    app.dependency_overrides.clear()


def test_settings_validation_redacts_an_overlong_api_key(db_session):
    app = create_app()
    supplied_key = "test-key-" + "x" * 5_000

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        response = api_client.put("/api/settings/ai", json=_provider_payload(supplied_key))

    assert response.status_code == 422
    assert supplied_key not in response.text
    assert "input" not in response.text
    app.dependency_overrides.clear()


def test_corrupted_encrypted_provider_falls_back_without_exposing_configuration(db_session):
    seed_database(db_session)
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        assert api_client.put("/api/settings/ai", json=_provider_payload()).status_code == 200
        stored = db_session.get(AIProviderConfig, 1)
        assert stored is not None
        stored.encrypted_api_key = "corrupted-ciphertext"
        db_session.commit()

        query = api_client.post("/api/query", json={"question": "本月各区域销售额排名如何？"})
        report = api_client.post(
            "/api/reports/generate", json={"report_type": "月报", "modules": ["overview"]}
        )
        tested = api_client.post(
            "/api/settings/ai/test", json=_provider_payload(api_key="")
        )

    assert query.status_code == 200
    query_data = query.json()["data"]
    assert query_data["engine"] == "local"
    assert query_data["provenance"] == "local_fallback"
    assert query_data["warning"] == {
        "code": "AI_CONFIGURATION_INVALID",
        "message": "AI 服务不可用，已切换到本地规则解析。",
    }
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["engine"] == "local"
    assert report_data["provenance"] == "local_fallback"
    assert report_data["warning"] == {
        "code": "AI_CONFIGURATION_INVALID",
        "message": "AI 叙述服务不可用，已保留本地报告内容。",
    }
    assert "AI 叙述不可用，报告已由本地业务数据和本地规则生成" in report_data[
        "markdown"
    ]
    assert tested.status_code == 400
    assert tested.json()["error"]["code"] == "AI_CONFIGURATION_INVALID"
    assert "corrupted-ciphertext" not in tested.text
    app.dependency_overrides.clear()


def test_health_tracks_enabled_provider_without_decrypting_its_key(db_session):
    seed_database(db_session)
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        assert api_client.put("/api/settings/ai", json=_provider_payload()).status_code == 200
        stored = db_session.get(AIProviderConfig, 1)
        assert stored is not None
        stored.encrypted_api_key = "corrupted-but-health-must-not-decrypt"
        db_session.commit()

        enabled = api_client.get("/api/health")
        disabled_payload = _provider_payload(api_key="")
        disabled_payload["enabled"] = False
        assert api_client.put("/api/settings/ai", json=disabled_payload).status_code == 200
        disabled = api_client.get("/api/health")

    assert enabled.status_code == 200
    assert enabled.json()["data"]["ai_mode"] == "ai"
    assert enabled.json()["data"]["provider"] == "Mock LLM"
    assert "corrupted-but-health-must-not-decrypt" not in enabled.text
    assert disabled.status_code == 200
    assert disabled.json()["data"]["ai_mode"] == "local"
    assert disabled.json()["data"]["provider"] is None
    app.dependency_overrides.clear()


def test_connection_uses_current_form_with_saved_key_without_mutating_saved_config(
    db_session, monkeypatch
):
    app = create_app()
    captured = {}

    class RecordingClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def test_connection(self):
            return None

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        assert api_client.put("/api/settings/ai", json=_provider_payload()).status_code == 200
        stored = db_session.get(AIProviderConfig, 1)
        assert stored is not None
        encrypted_api_key = stored.encrypted_api_key
        saved_values = (
            stored.provider_name,
            stored.base_url,
            stored.model,
            stored.timeout_seconds,
            stored.enabled,
            stored.allow_private_network,
        )
        monkeypatch.setattr("app.ai.service.OpenAICompatibleClient", RecordingClient)
        current_form = {
            "provider_name": "Current Form Provider",
            "base_url": "http://mock-llm:8090/v1",
            "api_key": "",
            "model": "current-form-model",
            "timeout_seconds": 17,
            "enabled": False,
            "allow_private_network": False,
        }

        response = api_client.post("/api/settings/ai/test", json=current_form)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "connected",
        "provider": "Current Form Provider",
        "model": "current-form-model",
        "latency_ms": response.json()["data"]["latency_ms"],
        "enabled": False,
        "allow_private_network": False,
    }
    assert captured == {
        "base_url": "http://mock-llm:8090/v1",
        "api_key": "test-key",
        "model": "current-form-model",
        "timeout_seconds": 17,
        "allow_private_network": False,
    }
    stored = db_session.get(AIProviderConfig, 1)
    assert stored is not None
    assert stored.encrypted_api_key == encrypted_api_key
    assert (
        stored.provider_name,
        stored.base_url,
        stored.model,
        stored.timeout_seconds,
        stored.enabled,
        stored.allow_private_network,
    ) == saved_values
    assert "test-key" not in response.text
    app.dependency_overrides.clear()


def test_blank_key_cannot_be_reused_for_a_different_base_url(db_session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        assert api_client.put("/api/settings/ai", json=_provider_payload()).status_code == 200
        changed = _provider_payload(api_key="")
        changed["base_url"] = "https://different-provider.example/v1"

        save_response = api_client.put("/api/settings/ai", json=changed)
        test_response = api_client.post("/api/settings/ai/test", json=changed)

    assert save_response.status_code == 400
    assert save_response.json()["error"]["code"] == "AI_API_KEY_REQUIRED"
    assert test_response.status_code == 400
    assert test_response.json()["error"]["code"] == "AI_API_KEY_REQUIRED"
    assert db_session.get(AIProviderConfig, 1).base_url == "http://mock-llm:8090/v1"
    app.dependency_overrides.clear()


def test_connection_test_accepts_empty_payload_using_saved_config(
    db_session, monkeypatch
):
    app = create_app()
    captured = {}

    class RecordingClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def test_connection(self):
            return None

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        assert api_client.put("/api/settings/ai", json=_provider_payload()).status_code == 200
        stored = db_session.get(AIProviderConfig, 1)
        encrypted_api_key = stored.encrypted_api_key
        monkeypatch.setattr("app.ai.service.OpenAICompatibleClient", RecordingClient)
        response = api_client.post("/api/settings/ai/test", json={})

    assert response.status_code == 200
    assert response.json()["data"]["provider"] == "Mock LLM"
    assert response.json()["data"]["model"] == "mock-model"
    assert captured == {
        "base_url": "http://mock-llm:8090/v1",
        "api_key": "test-key",
        "model": "mock-model",
        "timeout_seconds": 5,
        "allow_private_network": True,
    }
    assert db_session.get(AIProviderConfig, 1).encrypted_api_key == encrypted_api_key
    assert "test-key" not in response.text
    app.dependency_overrides.clear()


def test_deepseek_connection_test_reports_private_network_as_disabled(
    db_session, monkeypatch
):
    app = create_app()

    class RecordingClient:
        allow_private_network = False

        def __init__(self, **_kwargs):
            pass

        async def test_connection(self):
            return None

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        payload = _provider_payload(
            provider_name="DeepSeek",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            allow_private_network=True,
        )
        monkeypatch.setattr("app.ai.service.OpenAICompatibleClient", RecordingClient)
        response = api_client.post("/api/settings/ai/test", json=payload)

    assert response.status_code == 200
    assert response.json()["data"]["allow_private_network"] is False
    app.dependency_overrides.clear()


@pytest.mark.parametrize("payload", [{}, _provider_payload(api_key="")])
def test_connection_test_requires_a_key_before_any_provider_is_saved(
    db_session, payload
):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        response = api_client.post("/api/settings/ai/test", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AI_API_KEY_REQUIRED"
    app.dependency_overrides.clear()


def test_connection_test_rejects_a_partial_current_form(db_session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as api_client:
        response = api_client.post(
            "/api/settings/ai/test", json={"model": "partial-model"}
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
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
        report = api_client.post(
            "/api/reports/generate",
            json={"report_type": "月报", "modules": ["overview"]},
        )

        assert saved.status_code == 200
        assert result.status_code == 200
        data = result.json()["data"]
        assert data["engine"] == "local"
        assert data["provenance"] == "local_fallback"
        assert data["warning"] == {
            "code": "AI_BAD_RESPONSE",
            "message": "AI 服务不可用，已切换到本地规则解析。",
        }
        assert "test-key" not in result.text
        assert "8091" not in result.text
        report_data = report.json()["data"]
        assert report_data["engine"] == "local"
        assert report_data["provenance"] == "local_fallback"
        assert report_data["warning"] == {
            "code": "AI_BAD_RESPONSE",
            "message": "AI 叙述服务不可用，已保留本地报告内容。",
        }
        assert "test-key" not in report.text
        assert "8091" not in report.text

    app.dependency_overrides.clear()
