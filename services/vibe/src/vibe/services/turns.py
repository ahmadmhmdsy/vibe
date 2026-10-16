# services/vibe/src/vibe/services/turns.py
"""One turn, recorded once.

The chat route and the auto-run fix loop both run the agent, and before this
module only the first one recorded what happened: the fix loop iterated the
runtime's events and threw them away, so its tool calls, its prose and its
reasoning existed nowhere except the model's context. Both loops write the same
kind of history, so the append-and-publish shape lives here instead of twice.

Not used by the chat route yet: that one also handles abort and error turn
shapes, and adopting this helper is a separate cleanup. Its text_chunk handling
is deliberately identical to the route's -- streamed live, never stored.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from vibe.events import Event, EventBus, EventStore
from vibe.models import AgentEvent

#: Kinds kept in the log. text_chunk is absent on purpose: it is streamed and
#: never stored (see EventLog.next_seq), and a chunk is not a message.
_LOGGED = frozenset({"tool_call", "tool_result"})


class TurnRecorder:
    """Append-and-publish for one turn, so every loop logs the same way."""

    def __init__(self, session_id: str, event_log: EventStore, event_bus: EventBus):
        self._sid = session_id
        self._log = event_log
        self._bus = event_bus
        self._text: list[str] = []

    @property
    def text(self) -> str:
        """The prose streamed so far, in order."""
        return "".join(self._text)

    async def _publish(self, type_: str, payload: dict, seq: int) -> None:
        await self._bus.publish(self._sid, Event(session_id=self._sid, seq=seq,
                                                 type=type_, payload=payload))

    async def consume(self, events: AsyncIterator[AgentEvent]) -> str:
        """Record every event in a run, and return the prose it produced."""
        async for event in events:
            if event.kind in _LOGGED:
                seq = await self._log.append(self._sid, event.kind, event.data)
                await self._publish(event.kind, event.data, seq)
            elif event.kind == "text_chunk":
                self._text.append(event.data.get("text", ""))
                await self._publish("text_chunk", event.data, self._log.next_seq(self._sid))
            elif event.kind == "turn_complete":
                await self._publish("turn_complete", event.data, self._log.next_seq(self._sid))
        return self.text
