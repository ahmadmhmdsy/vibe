# tests/test_providers.py
import pytest
from vibe.providers.base import LlmProvider, ChatRequest, ChatEvent
from vibe.providers.catalog import ProviderCatalog
from vibe.models import Message, ModelRef, ToolSchema

class StubProvider:
    id = "stub"
    async def chat(self, request):
        yield ChatEvent(kind="text_chunk", data={"text": "hi"})
        yield ChatEvent(kind="usage", data={"input_tokens": 10, "output_tokens": 5})
        yield ChatEvent(kind="done", data={})

@pytest.mark.asyncio
async def test_stub_provider_streams_events():
    p = StubProvider()
    req = ChatRequest(messages=[Message(role="user", content="hi")], tools=[], model=ModelRef("stub", "m"))
    events = [e async for e in p.chat(req)]
    kinds = [e.kind for e in events]
    assert "text_chunk" in kinds
    assert "usage" in kinds

def test_catalog_exposes_no_keys():
    cat = ProviderCatalog()
    providers = cat.list_providers()
    assert len(providers) > 0
    for p in providers:
        assert "apiKey" not in p
        assert "baseUrl" not in p
        assert "id" in p and "name" in p
