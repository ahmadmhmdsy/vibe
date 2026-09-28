# tests/test_runtime.py
import pytest
from vibe.runtime.base import AgentContext, AgentRuntime
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.models import AgentInput, AgentEvent, Message, ModelRef, ToolCall
from vibe.events import EventBus
from vibe.store import SessionStore
from pathlib import Path

class StubLlm:
    """Yields one text_chunk then turn_complete (no tools)."""
    def __init__(self, responses):
        self._responses = list(responses)
    def bind_tools(self, tools):
        return self
    def invoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self._responses.pop(0))

class StubToolRegistry:
    def to_langchain_tools(self, ctx):
        return []

@pytest.mark.asyncio
async def test_langgraph_runtime_yields_text_and_turn_complete(tmp_path):
    llm = StubLlm(["hello world"])
    runtime = LangGraphRuntime(llm_factory=lambda m: llm, tool_registry=StubToolRegistry())
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=None,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    inp = AgentInput(session_id="s1", messages=[Message(role="user", content="hi")],
                     model=ModelRef(provider_id="openai", model_id="gpt-4o"))
    events = [e async for e in runtime.run(inp, ctx)]
    kinds = [e.kind for e in events]
    assert "text_chunk" in kinds
    assert "turn_complete" in kinds
    text = "".join(e.data.get("text", "") for e in events if e.kind == "text_chunk")
    assert "hello world" in text
