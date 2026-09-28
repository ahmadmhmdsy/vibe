# tests/test_usage.py
import pytest
from vibe.usage.tracker import UsageTracker, UsageAggregate
from vibe.events import EventLog, EventBus
from vibe.models import UsageRecord

@pytest.mark.asyncio
async def test_record_and_aggregate():
    log = EventLog()
    bus = EventBus()
    tracker = UsageTracker(log, bus)
    u = UsageRecord(provider="openai", model="gpt-4o", input_tokens=100, output_tokens=50,
                    cached_tokens=80, cache_write_tokens=0, cache_hit=True,
                    cache_hit_rate=0.44, total_tokens=230, cost_usd=0.01)
    await tracker.record("s1", u)
    total = await tracker.session_total("s1")
    assert total.input_tokens == 100
    assert total.output_tokens == 50
    assert total.cost_usd == 0.01
    assert total.steps == 1

@pytest.mark.asyncio
async def test_record_broadcasts_event():
    log = EventLog()
    bus = EventBus()
    tracker = UsageTracker(log, bus)
    u = UsageRecord(provider="openai", model="gpt-4o", input_tokens=10, output_tokens=5,
                    cached_tokens=0, cache_write_tokens=0, cache_hit=False,
                    cache_hit_rate=0.0, total_tokens=15, cost_usd=0.001)
    await tracker.record("s1", u)
    events = await log.get("s1")
    assert any(e.type == "usage" for e in events)
