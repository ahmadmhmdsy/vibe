from fastapi.testclient import TestClient
from vibe.api.app import create_app

def test_health_returns_200():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
