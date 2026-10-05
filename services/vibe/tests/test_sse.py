# tests/test_sse.py
# SSE endpoint tests. TestClient/ASGITransport cannot test an infinite SSE
# stream (it awaits the full response inline), so these tests drive the route
# function directly with a mock request and iterate the StreamingResponse
# body_iterator, cancelling after the expected events.
import asyncio
import contextlib

import pytest

from vibe.api.errors import ApiError, ErrorCode
from vibe.api.routes.sessions import events
from vibe.api.sse import format_sse
from vibe.events import Event, EventBus, EventLog


class _QueryParams:
    def __init__(self, d=None):
        self._d = d or {}
    def get(self, key, default=None):
        return self._d.get(key, default)


class _Store:
    """Only the sessions that exist resolve; anything else is a 404."""
    def __init__(self, known=("s1",)):
        self._known = set(known)
    async def get_session(self, sid):
        return {"id": sid} if sid in self._known else None


class _State:
    def __init__(self, known=("s1",)):
        self.event_log = EventLog()
        self.event_bus = EventBus()
        self.store = _Store(known)


class _App:
    def __init__(self, known=("s1",)):
        self.state = _State(known)


class _Request:
    def __init__(self, app, query_params=None):
        self.app = app
        self.query_params = query_params or _QueryParams()


async def _collect(resp, count, timeout=2.0):
    """Consume up to `count` chunks, then stop."""
    received = []

    async def consume():
        async for chunk in resp.body_iterator:
            received.append(chunk)
            if len(received) >= count:
                return

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except TimeoutError:
        task.cancel()
    return received


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
    resp = await events("s1", req, app.state)
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
    resp = await events("s1", req, app.state)
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
    with contextlib.suppress(asyncio.CancelledError):
        await task
    # only the event with seq > 1 should be replayed
    assert any("assistant/message" in c for c in received)
    assert not any("user/message" in c for c in received)


@pytest.mark.asyncio
async def test_sse_does_not_deliver_a_logged_event_twice():
    """A logged event is both replayed and published; the client must see one copy.

    The bus used to hold every published event until someone connected, so a
    client that reconnected mid-run received the replayed log copy *and* the
    queued live copy of the same tool call.
    """
    app = _App()
    log = app.state.event_log
    bus = app.state.event_bus
    await log.append("s1", "user/message", {"content": "hi"})  # seq 1
    req = _Request(app)
    resp = await events("s1", req, app.state)

    task = asyncio.create_task(_collect(resp, 2))
    await asyncio.sleep(0.02)
    # Re-publish the same seq the replay already delivered, then a genuinely new one.
    await bus.publish("s1", Event(session_id="s1", seq=1, type="user/message", payload={"content": "hi"}))
    await bus.publish("s1", Event(session_id="s1", seq=2, type="text_chunk", payload={"text": "live"}))
    received = await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 2
    assert sum("user/message" in c for c in received) == 1
    assert any("text_chunk" in c for c in received)
    task.cancel()


@pytest.mark.asyncio
async def test_sse_rejects_invalid_after_seq():
    app = _App()
    req = _Request(app, _QueryParams({"after_seq": "not-a-number"}))
    with pytest.raises(ApiError) as err:
        await events("s1", req, app.state)
    assert err.value.status == 400
    assert err.value.code is ErrorCode.VALIDATION_FAILED


@pytest.mark.asyncio
async def test_sse_404_for_unknown_session():
    app = _App()
    req = _Request(app)
    with pytest.raises(ApiError) as err:
        await events("nope", req, app.state)
    assert err.value.status == 404
    assert err.value.code is ErrorCode.SESSION_NOT_FOUND
