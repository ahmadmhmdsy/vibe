# services/vibe/src/vibe/usage/tracker.py
from __future__ import annotations
from dataclasses import dataclass, field
from vibe.models import UsageRecord
from vibe.events import EventLog, EventBus

@dataclass
class UsageAggregate:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    steps: int = 0

class UsageTracker:
    def __init__(self, log: EventLog, bus: EventBus):
        self._log = log
        self._bus = bus

    async def record(self, session_id: str, usage: UsageRecord) -> None:
        await self._log.append(session_id, "usage", usage.__dict__)
        from vibe.events import Event
        events = await self._log.get(session_id)
        seq = events[-1].seq if events else 0
        await self._bus.publish(session_id, Event(session_id=session_id, seq=seq, type="usage", payload=usage.__dict__))

    async def session_total(self, session_id: str) -> UsageAggregate:
        total = UsageAggregate()
        for e in await self._log.get(session_id):
            if e.type == "usage":
                u = UsageRecord(**e.payload)
                total.input_tokens += u.input_tokens
                total.output_tokens += u.output_tokens
                total.cached_tokens += u.cached_tokens
                total.total_tokens += u.total_tokens
                total.cost_usd += u.cost_usd
                total.steps += 1
        return total
