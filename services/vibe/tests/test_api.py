
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # The resolved paths are the point of this endpoint: an un-expanded
    # VIBE_WORKSPACE_DIR used to make the same install look empty depending on
    # the directory the server was launched from.
    assert body["workspace_dir"]
    assert body["sessions_db"].startswith(body["workspace_dir"])
    assert body["events_db"].startswith(body["workspace_dir"])

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

def test_file_sync_write_read_list(client):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # write a file (hand-edit sync)
    resp = client.put(f"/sessions/{sid}/files/src/App.tsx", json={"content": "export default function App() { return <div>hi</div> }"})
    assert resp.status_code == 200
    # read it back
    resp = client.get(f"/sessions/{sid}/files/src/App.tsx")
    assert resp.status_code == 200
    assert "hi" in resp.json()["content"]
    # list files
    resp = client.get(f"/sessions/{sid}/files")
    assert resp.status_code == 200
    assert "src/App.tsx" in resp.json()


def test_file_sync_rejects_path_outside_workspace(client):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # The traversal is rejected — either by URL normalization (405) or by the
    # workspace check in _safe_file (400). Both are safe (no file written).
    resp = client.put(f"/sessions/{sid}/files/../../escape.txt", json={"content": "x"})
    assert resp.status_code in (400, 405)


def test_catalog(client):
    resp = client.get("/catalog")
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) > 0
    for p in providers:
        assert "apiKey" not in p
