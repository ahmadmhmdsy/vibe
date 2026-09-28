# tests/test_sse.py
# SSE endpoint tests. TestClient/ASGITransport cannot test an infinite SSE
# stream (it awaits the full response inline), so these tests drive the route
# function directly with a mock request and iterate the StreamingResponse
# body_iterator, cancelling after the expected events.
import asyncio
import pytest
from vibe.api.sse import format_sse
from vibe.api.routes.sessions import events
from vibe.events import EventLog, EventBus, Event


class _QueryParams:
    def __init__(self, d=None):
        self._d = d or {}
    def get(self, key, default=None):
        return self._d.get(key, default)


class _State:
    def __init__(self):
        self.event_log = EventLog()
        self.event_bus = EventBus()


class _App:
    def __init__(self):
        self.state = _State()


class _Request:
    def __init__(self, app, query_params=None):
        self.app = app
        self.query_params = query_params or _QueryParams()


def test_format_sse_wire_format():
    e = Event(session_id="s1", seq=1, type="user/message", payload={"content": "hi"})
    out = format_sse(e)
    assert out.startswith("data: ")
    assert '"seq": 1' in out
    assert '"type": "user/message"' in out
    assert out.endswith("\n\n")


@pytest.mark.asyncio
async def test_sse_replays_log_then_live_streams():
    app = _App()
    log = app.state.event_log
    bus = app.state.event_bus
    await log.append("s1", "user/message", {"content": "hi"})
    req = _Request(app)
    resp = await events("s1", req)
    assert resp.media_type == "text/event-stream"
    received = []

    async def consume():
        async for chunk in resp.body_iterator:
            received.append(chunk)
            if len(received) >= 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.02)
    await bus.publish("s1", Event(session_id="s1", seq=2, type="text_chunk", payload={"text": "hello"}))
    await asyncio.wait_for(task, timeout=2.0)
    assert any("user/message" in c for c in received)
    assert any("text_chunk" in c for c in received)


@pytest.mark.asyncio
async def test_sse_replay_respects_after_seq():
    app = _App()
    log = app.state.event_log
    await log.append("s1", "user/message", {"content": "hi"})
    await log.append("s1", "assistant/message", {"content": "hello"})
    req = _Request(app, _QueryParams({"after_seq": "1"}))
    resp = await events("s1", req)
    received = []

    async def consume():
        async for chunk in resp.body_iterator:
            received.append(chunk)
            if len(received) >= 1:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.02)
    # cancel the infinite generator after the first replayed chunk
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    # only the event with seq > 1 should be replayed
    assert any("assistant/message" in c for c in received)
    assert not any("user/message" in c for c in received)
