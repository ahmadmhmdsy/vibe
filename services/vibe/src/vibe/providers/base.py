# services/vibe/src/vibe/providers/base.py
from __future__ import annotations
from typing import Protocol, AsyncIterator
from vibe.models import ChatRequest, ChatEvent

class LlmProvider(Protocol):
    id: str
    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]: ...
