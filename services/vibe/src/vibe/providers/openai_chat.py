# services/vibe/src/vibe/providers/openai_chat.py
from __future__ import annotations
from typing import AsyncIterator
from vibe.models import ChatRequest, ChatEvent, UsageRecord
from vibe.providers.base import LlmProvider

class OpenAIChatProvider(LlmProvider):
    id = "openai"
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
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
