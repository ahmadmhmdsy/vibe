# services/vibe/src/vibe/services/messages.py
"""Chat history as a projection over the event log.

The log is the source of truth ("model-visible means logged"); the ordered
user/assistant transcript is derived from it rather than stored separately, so a
replayed history and a live one cannot disagree.
"""
from __future__ import annotations

from dataclasses import dataclass

from vibe.events import EventStore
from vibe.models import Message

# A failed turn is recorded as assistant/error so history shows why a user
# message has no answer instead of dangling. It reads as an assistant turn.
_MESSAGE_TYPES = {
    "user/message": "user",
    "assistant/message": "assistant",
    "assistant/error": "assistant",
}


@dataclass(frozen=True)
class MessagePage:
    """One page of a session's transcript, oldest first within the page."""

    messages: list[Message]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        """True while older messages remain before this page."""
        return self.offset + len(self.messages) < self.total


class MessageService:
    def __init__(self, event_log: EventStore):
        self._log = event_log

    async def page(self, sid: str, *, limit: int = 200, offset: int = 0) -> MessagePage:
        """The transcript for a session, newest last.

        `offset` counts back from the most recent message, which is what a chat
        client wants: offset 0 is the latest page and offset `limit` the one
        before it. Returning everything is what a long conversation used to
        cost, on every open, whether or not the user scrolled back.
        """
        everything = self._project(await self._log.get(sid))
        total = len(everything)
        end = max(total - offset, 0)
        start = max(end - limit, 0)
        return MessagePage(messages=everything[start:end], total=total, offset=offset, limit=limit)

    async def history(self, sid: str, *, limit: int = 200, offset: int = 0) -> list[Message]:
        """Just the messages, for a caller that does not care about the count."""
        return (await self.page(sid, limit=limit, offset=offset)).messages

    @staticmethod
    def _project(events) -> list[Message]:
        messages: list[Message] = []
        for e in events:
            role = _MESSAGE_TYPES.get(e.type)
            if role is None:
                continue
            content = e.payload.get("content", "")
            if content:
                messages.append(Message(role=role, content=content))
        return messages
