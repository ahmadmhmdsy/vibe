# services/vibe/tests/test_messages_endpoint.py
import asyncio


def _seed_messages(app, sid):
    async def seed():
        await app.state.container.event_log.append(sid, "user/message", {"content": "hello"})
        await app.state.container.event_log.append(sid, "assistant/message", {"content": "hi there"})
        await app.state.container.event_log.append(sid, "user/message", {"content": "build a todo app"})
        await app.state.container.event_log.append(sid, "assistant/message", {"content": "done"})

    asyncio.run(seed())


def test_messages_endpoint_returns_history(client, app):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    _seed_messages(app, sid)
    resp = client.get(f"/sessions/{sid}/messages")
    assert resp.status_code == 200
    assert resp.json() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "build a todo app"},
        {"role": "assistant", "content": "done"},
    ]


def test_messages_endpoint_empty_for_new_session(client):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    resp = client.get(f"/sessions/{sid}/messages")
    assert resp.status_code == 200
    assert resp.json() == []


def test_messages_endpoint_pages_back_from_the_latest(client, app):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    _seed_messages(app, sid)
    resp = client.get(f"/sessions/{sid}/messages?limit=2")
    assert resp.status_code == 200
    assert resp.json() == [
        {"role": "user", "content": "build a todo app"},
        {"role": "assistant", "content": "done"},
    ]


def test_messages_endpoint_offset_walks_backwards(client, app):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    _seed_messages(app, sid)
    resp = client.get(f"/sessions/{sid}/messages?limit=2&offset=2")
    assert resp.status_code == 200
    assert resp.json() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_messages_endpoint_reports_the_total_in_a_header(client, app):
    """The count travels in a header so the array stays the response body, as it
    is for every other collection this API returns."""
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    _seed_messages(app, sid)
    resp = client.get(f"/sessions/{sid}/messages?limit=2")
    assert resp.headers["x-total-count"] == "4"
    assert len(resp.json()) == 2


def test_messages_endpoint_rejects_an_out_of_range_limit(client, app):
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # R2-T1 unified validation failures on 400 (was FastAPI's bare 422).
    assert client.get(f"/sessions/{sid}/messages?limit=0").status_code == 400
    assert client.get(f"/sessions/{sid}/messages?limit=99999").status_code == 400
