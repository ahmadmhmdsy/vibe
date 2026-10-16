
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

def test_delete_says_the_workspace_is_busy_instead_of_failing_generically(client, monkeypatch):
    """A locked workspace used to be an unhandled PermissionError: HTTP 500.

    The acceptance run hit exactly this (a preview still holding a file in the
    session workspace) and got {"code": "internal"}, which tells the user
    nothing and hides that the session is still there. It is now a named 409.
    """
    from pathlib import Path

    from vibe import lifecycle as lifecycle_module

    monkeypatch.setattr(lifecycle_module, "_TRASH_MOVE_DELAY", 0)
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    workspace = Path(client.get("/health").json()["workspace_dir"]) / sid
    workspace.mkdir(parents=True, exist_ok=True)

    def boom(self, target):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "rename", boom)

    resp = client.delete(f"/sessions/{sid}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "workspace_busy"
    # The session is untouched: the caller can close the program holding it and
    # delete again, which is the whole point of not reporting a generic 500.
    assert client.get(f"/sessions/{sid}").status_code == 200


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
