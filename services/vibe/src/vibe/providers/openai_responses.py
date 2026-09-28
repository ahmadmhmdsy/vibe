# services/vibe/src/vibe/providers/openai_responses.py
from __future__ import annotations
from typing import AsyncIterator
from vibe.models import ChatRequest, ChatEvent
from vibe.providers.base import LlmProvider

class OpenAIResponsesProvider(LlmProvider):
    """OpenCode Go's Grok / GPT-Luna / Muse models use /v1/responses."""
    id = "opencode-go"
    def __init__(self, api_key: str, base_url: str = "https://opencode.ai/zen/go/v1"):
        from langchain_openai import ChatOpenAI
        self._model = ChatOpenAI(api_key=api_key, base_url=base_url, streaming=True)

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        msgs = []
        for m in request.messages:
            if m.role == "user": msgs.append(HumanMessage(content=m.content))
            elif m.role == "system": msgs.append(SystemMessage(content=m.content))
            elif m.role == "assistant": msgs.append(AIMessage(content=m.content))
        async for chunk in self._model.astream(msgs):
            if chunk.content:
                yield ChatEvent(kind="text_chunk", data={"text": chunk.content})
        yield ChatEvent(kind="done", data={})
