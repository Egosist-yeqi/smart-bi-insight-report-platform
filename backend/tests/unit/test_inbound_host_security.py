from fastapi.testclient import TestClient

from app.main import create_app


def test_backend_accepts_only_local_and_test_hosts():
    with TestClient(create_app()) as client:
        assert client.get("/api/openapi.json").status_code == 200
        assert client.get(
            "/api/openapi.json", headers={"Host": "localhost:8000"}
        ).status_code == 200
        assert client.get(
            "/api/openapi.json", headers={"Host": "127.0.0.1:8000"}
        ).status_code == 200
        assert client.get(
            "/api/openapi.json", headers={"Host": "attacker.example"}
        ).status_code == 400
