# services/vibe/src/vibe/usage/tracker.py
from __future__ import annotations

from dataclasses import dataclass

from vibe.events import EventBus, EventStore
from vibe.models import UsageRecord


@dataclass
class UsageAggregate:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    steps: int = 0


@dataclass
class ModelUsage:
    """One row of the per-model breakdown the usage endpoint reports."""

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    steps: int = 0


class UsageTracker:
    def __init__(self, log: EventStore, bus: EventBus):
        self._log = log
        self._bus = bus

    async def record(self, session_id: str, usage: UsageRecord) -> None:
        # append() returns the seq it assigned; re-reading the log to find it
        # was an O(events) scan on every single model call.
        seq = await self._log.append(session_id, "usage", usage.__dict__)
        from vibe.events import Event

        await self._bus.publish(session_id, Event(session_id=session_id, seq=seq, type="usage", payload=usage.__dict__))

    async def _records(self, session_id: str) -> list[UsageRecord]:
        return [UsageRecord(**e.payload) for e in await self._log.get(session_id) if e.type == "usage"]

    async def session_total(self, session_id: str) -> UsageAggregate:
        total = UsageAggregate()
        for u in await self._records(session_id):
            total.input_tokens += u.input_tokens
            total.output_tokens += u.output_tokens
            total.cached_tokens += u.cached_tokens
            total.cache_write_tokens += u.cache_write_tokens
            total.total_tokens += u.total_tokens
            total.cost_usd += u.cost_usd
            total.steps += 1
        return total

    async def session_by_model(self, session_id: str) -> list[ModelUsage]:
        """Per-model totals, ordered by first appearance in the log."""
        rows: dict[tuple[str, str], ModelUsage] = {}
        for u in await self._records(session_id):
            row = rows.get((u.provider, u.model))
            if row is None:
                row = rows[(u.provider, u.model)] = ModelUsage(provider=u.provider, model=u.model)
            row.input_tokens += u.input_tokens
            row.output_tokens += u.output_tokens
            row.cached_tokens += u.cached_tokens
            row.cache_write_tokens += u.cache_write_tokens
            row.total_tokens += u.total_tokens
            row.cost_usd += u.cost_usd
            row.steps += 1
        return list(rows.values())
