from fastapi.testclient import TestClient

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

def test_create_and_list_sessions(client):
    resp = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})
    assert resp.status_code == 201
    sid = resp.json()["id"]
    assert sid
    resp2 = client.get("/sessions")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1

def test_send_message_runs_agent(client):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "build a todo app"})
    assert resp.status_code == 200
    assert "hello from agent" in resp.json()["content"]

def test_rename_and_delete_session(client):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    resp = client.patch(f"/sessions/{sid}", json={"title": "My App"})
    assert resp.status_code == 200
    resp = client.delete(f"/sessions/{sid}")
    assert resp.status_code == 204

def test_catalog(client):
    resp = client.get("/catalog")
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) > 0
    for p in providers:
        assert "apiKey" not in p
