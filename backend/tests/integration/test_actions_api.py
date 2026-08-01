from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import create_app


def test_action_lifecycle_requires_a_review_before_completion(db_session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        created = client.post(
            "/api/actions",
            json={
                "title": "核查华东区域经营金额异动",
                "owner": "区域运营负责人",
                "priority": "high",
                "due_date": "2026-07-15",
                "target_metric": "经营金额",
                "source_type": "anomaly",
                "evidence": "华东区域月度金额下降超过阈值。",
            },
        )
        action_id = created.json()["data"]["id"]
        refused = client.patch(
            f"/api/actions/{action_id}", json={"status": "completed"}
        )
        in_progress = client.patch(
            f"/api/actions/{action_id}", json={"status": "in_progress"}
        )
        completed = client.patch(
            f"/api/actions/{action_id}",
            json={"status": "completed", "review_notes": "已完成客户和产品结构核查，后续按周复盘。"},
        )
        listed = client.get("/api/actions")
    app.dependency_overrides.clear()

    assert created.status_code == 200
    assert created.json()["data"]["status"] == "open"
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "ACTION_REVIEW_REQUIRED"
    assert in_progress.status_code == 200
    assert completed.status_code == 200
    assert completed.json()["data"]["status"] == "completed"
    assert listed.status_code == 200
    assert listed.json()["data"]["summary"] == {
        "open": 0,
        "in_progress": 0,
        "completed": 1,
        "overdue": 0,
    }


def test_action_api_rejects_unknown_fields_and_returns_not_found(db_session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        invalid = client.post("/api/actions", json={"title": "测试", "untrusted": "value"})
        missing = client.patch("/api/actions/99999", json={"status": "in_progress"})
    app.dependency_overrides.clear()

    assert invalid.status_code == 422
    assert "value" not in invalid.text
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACTION_NOT_FOUND"
