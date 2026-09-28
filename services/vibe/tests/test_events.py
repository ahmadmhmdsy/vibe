# tests/test_events.py
import pytest
from vibe.events import EventLog, EventBus, Event

@pytest.mark.asyncio
async def test_event_log_append_and_get():
    log = EventLog()
    seq = await log.append("s1", "user/message", {"content": "hi"})
    assert seq == 1
    events = await log.get("s1")
    assert len(events) == 1
    assert events[0].type == "user/message"
    assert events[0].payload == {"content": "hi"}

@pytest.mark.asyncio
async def test_event_log_get_after_seq():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "hi"})
    await log.append("s1", "assistant/message", {"content": "hello"})
    events = await log.get("s1", after_seq=1)
    assert len(events) == 1
    assert events[0].type == "assistant/message"

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []
    async def consume():
        async for e in bus.subscribe("s1"):
            received.append(e)
            if len(received) >= 1:
                break
    import asyncio
    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.publish("s1", Event(session_id="s1", seq=1, type="user/message", payload={}))
    await asyncio.wait_for(task, timeout=1.0)
    assert received[0].type == "user/message"
