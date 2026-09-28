# services/vibe/src/vibe/events.py
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

@dataclass
class Event:
    session_id: str
    seq: int
    type: str
    payload: dict[str, Any]

class EventLog:
    """In-memory append-only log. SQLite persistence lands in Task 4."""
    def __init__(self):
        self._events: dict[str, list[Event]] = {}
        self._seq: dict[str, int] = {}

    async def append(self, session_id: str, type: str, payload: dict[str, Any]) -> int:
        seq = self._seq.get(session_id, 0) + 1
        self._seq[session_id] = seq
        event = Event(session_id=session_id, seq=seq, type=type, payload=payload)
        self._events.setdefault(session_id, []).append(event)
        return seq

    async def get(self, session_id: str, after_seq: int = 0) -> list[Event]:
        return [e for e in self._events.get(session_id, []) if e.seq > after_seq]

class EventBus:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue[Event]] = {}

    def _queue(self, session_id: str) -> asyncio.Queue[Event]:
        return self._queues.setdefault(session_id, asyncio.Queue())

    async def publish(self, session_id: str, event: Event) -> None:
        await self._queue(session_id).put(event)

    async def subscribe(self, session_id: str) -> AsyncIterator[Event]:
        q = self._queue(session_id)
        try:
            while True:
                event = await q.get()
                yield event
        except asyncio.CancelledError:
            raise
