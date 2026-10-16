# services/vibe/tests/test_preview_endpoint.py
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.runs import SessionKey


class _StubExecutor:
    """In-memory executor: no real subprocesses."""

    def __init__(self):
        self._dev_server = None

    @property
    def dev_server_url(self):
        return self._dev_server.url if self._dev_server else None

    async def start_dev_server(self):
        from vibe.executor.base import DevServerHandle
        self._dev_server = DevServerHandle(port=5173, url="http://127.0.0.1:5173/", process=None)
        return self._dev_server

    async def stop_dev_server(self):
        self._dev_server = None

    async def close(self):
        self._dev_server = None


def test_preview_run_status_stop(client, app):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # The executor registry is keyed by (owner, session); keyed by the bare id
    # the route would find nothing and build a real subprocess executor.
    app.state.container.executors[
        SessionKey(owner_id=LOOPBACK_OWNER_ID, session_id=sid)
    ] = _StubExecutor()

    # Initially: no dev server.
    resp = client.get(f"/sessions/{sid}/preview")
    assert resp.status_code == 200
    assert resp.json() == {"url": None, "is_running": False}

    # Run starts the dev server.
    resp = client.post(f"/sessions/{sid}/preview/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_running"] is True
    assert body["url"]

    # Status reflects the running server.
    resp = client.get(f"/sessions/{sid}/preview")
    assert resp.json()["is_running"] is True
    assert resp.json()["url"] == body["url"]

    # Stop shuts it down.
    resp = client.post(f"/sessions/{sid}/preview/stop")
    assert resp.status_code == 200
    assert resp.json() == {"url": None, "is_running": False}

    # Status confirms it is gone.
    resp = client.get(f"/sessions/{sid}/preview")
    assert resp.json() == {"url": None, "is_running": False}
