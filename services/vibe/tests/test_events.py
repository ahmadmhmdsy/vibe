# tests/test_events.py
import pytest

from vibe.events import Event, EventBus, EventLog, EventStore
from vibe.models import UsageRecord
from vibe.usage.tracker import UsageTracker


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


@pytest.mark.asyncio
async def test_event_bus_fans_out_to_every_subscriber():
    """Two tabs (or a reconnect overlapping its predecessor) each see the whole stream.

    A single shared queue per session made subscribers compete: each got a
    random subset of the events.
    """
    bus = EventBus()
    first = bus.subscribe("s1")
    second = bus.subscribe("s1")
    for seq in (1, 2, 3):
        await bus.publish("s1", Event(session_id="s1", seq=seq, type="text_chunk", payload={"text": str(seq)}))
    assert [e.seq for e in first.pending()] == [1, 2, 3]
    assert [e.seq for e in second.pending()] == [1, 2, 3]
    assert bus.subscriber_count == 2


@pytest.mark.asyncio
async def test_event_bus_does_not_backlog_for_a_future_subscriber():
    """Events published with nobody listening are not replayed on connect.

    The old queue kept them, so the next client received stale events mixed
    into the live stream — on top of the copies the log replay already sent.
    """
    bus = EventBus()
    await bus.publish("s1", Event(session_id="s1", seq=1, type="text_chunk", payload={}))
    assert bus.subscribe("s1").pending() == []


@pytest.mark.asyncio
async def test_subscription_close_unregisters_and_is_idempotent():
    bus = EventBus()
    sub = bus.subscribe("s1")
    assert bus.subscriber_count == 1
    await sub.aclose()
    await sub.aclose()
    assert bus.subscriber_count == 0
    # a closed subscription stops iterating instead of hanging
    with pytest.raises(StopAsyncIteration):
        await sub.__anext__()


@pytest.mark.asyncio
async def test_ephemeral_seq_advances_without_being_stored():
    """Streamed chunks need a monotonic seq but must not bloat the log."""
    log = EventLog()
    assert await log.append("s1", "user/message", {"content": "hi"}) == 1
    assert log.next_seq("s1") == 2          # a text_chunk, not stored
    assert log.next_seq("s1") == 3          # turn_complete, not stored
    assert await log.append("s1", "assistant/message", {"content": "yo"}) == 4
    stored = await log.get("s1")
    assert [e.seq for e in stored] == [1, 4]
    assert log.last_seq("s1") == 4


def test_event_log_satisfies_the_event_store_protocol(tmp_path):
    """Consumers are typed against EventStore, so EventLog must keep matching it.

    A rename or signature change on EventLog would silently break that contract
    (the annotations are erased at runtime), so assert it explicitly.
    """
    assert isinstance(EventLog(), EventStore)
    assert isinstance(EventLog(tmp_path / "events.db"), EventStore)


@pytest.mark.asyncio
async def test_a_fake_event_store_can_stand_in_for_the_real_one():
    """The point of the protocol: callers can be given something else."""

    class FakeStore:
        def __init__(self):
            self.appended = []

        def next_seq(self, session_id):
            return len(self.appended) + 1

        async def append(self, session_id, type, payload):
            self.appended.append((session_id, type, payload))
            return self.next_seq(session_id)

        async def get(self, session_id, after_seq=0):
            return []

        def last_seq(self, session_id):
            return len(self.appended)

        def clear(self, session_id):
            self.appended.clear()

        def close(self):
            pass

    fake = FakeStore()
    assert isinstance(fake, EventStore)
    tracker = UsageTracker(log=fake, bus=EventBus())
    usage = UsageRecord(provider="openai", model="gpt-4o", input_tokens=1, output_tokens=2,
                        cached_tokens=0, cache_write_tokens=0, cache_hit=False,
                        cache_hit_rate=0.0, total_tokens=3, cost_usd=0.0)
    await tracker.record("s1", usage)
    assert fake.appended and fake.appended[0][1] == "usage"
