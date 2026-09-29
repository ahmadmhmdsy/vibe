# services/vibe/tests/test_messages_endpoint.py
import asyncio


def _seed_messages(app, sid):
    async def seed():
        await app.state.event_log.append(sid, "user/message", {"content": "hello"})
        await app.state.event_log.append(sid, "assistant/message", {"content": "hi there"})
        await app.state.event_log.append(sid, "user/message", {"content": "build a todo app"})
        await app.state.event_log.append(sid, "assistant/message", {"content": "done"})

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
