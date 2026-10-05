# tests/test_runtime.py

import pytest

from vibe.events import EventBus
from vibe.models import AgentInput, Attachment, Message, ModelRef, ToolResult, ToolSchema
from vibe.runtime.base import AgentContext
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.store import SessionStore
from vibe.tools.registry import ToolRegistry


class StubLlm:
    """Yields one text_chunk then turn_complete (no tools)."""
    def __init__(self, responses):
        self._responses = list(responses)
    def bind_tools(self, tools):
        return self
    def invoke(self, messages):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self._responses.pop(0))

    async def ainvoke(self, messages):
        return self.invoke(messages)

class StubToolRegistry:
    def to_langchain_tools(self, ctx):
        return []

@pytest.mark.asyncio
async def test_langgraph_runtime_yields_text_and_turn_complete(tmp_path):
    llm = StubLlm(["hello world"])
    runtime = LangGraphRuntime(llm_factory=lambda m, session_id=None: llm, tool_registry=StubToolRegistry())
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


def test_to_lc_message_multimodal_with_attachment():
    from vibe.runtime.langgraph import _to_lc_message
    m = Message(role="user", content="build this",
                attachments=[Attachment(name="ref.png", content_type="image/png", data_base64="aGVsbG8=")])
    lc = _to_lc_message(m)
    assert lc.type == "human"
    assert isinstance(lc.content, list)
    assert lc.content[0] == {"type": "text", "text": "build this"}
    assert lc.content[1]["type"] == "image_url"
    assert "data:image/png;base64,aGVsbG8=" in lc.content[1]["image_url"]["url"]


class _ToolCallingLlm:
    """Calls one tool, then answers. Enough to drive the real graph."""

    def __init__(self, tool_name: str):
        self._tool_name = tool_name
        self._n = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        self._n += 1
        if self._n == 1:
            return AIMessage(content="", tool_calls=[
                {"name": self._tool_name, "args": {}, "id": "c1", "type": "tool_call"}])
        return AIMessage(content="done")


async def _run_one_tool(tmp_path, reg, tool_name):
    runtime = LangGraphRuntime(llm_factory=lambda m, session_id=None: _ToolCallingLlm(tool_name),
                               tool_registry=reg)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=None,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    inp = AgentInput(session_id="s1", messages=[Message(role="user", content="hi")],
                     model=ModelRef(provider_id="openai", model_id="gpt-4o"))
    events = [e async for e in runtime.run(inp, ctx)]
    return [e for e in events if e.kind == "tool_result"]


@pytest.mark.asyncio
async def test_tool_error_reaches_the_event_stream(tmp_path):
    """is_error was hardcoded False in the event, so a failing tool looked fine."""
    reg = ToolRegistry()

    async def boom(args, ctx):
        return ToolResult("", "boom", "kaboom", is_error=True)

    reg.register("boom", ToolSchema("boom", "boom", {"type": "object", "properties": {}}), boom)
    results = await _run_one_tool(tmp_path, reg, "boom")
    assert len(results) == 1
    assert results[0].data["is_error"] is True
    assert results[0].data["content"] == "kaboom"


@pytest.mark.asyncio
async def test_image_tool_result_keeps_the_event_text_only(tmp_path):
    """The image must reach the model but not the SSE transcript."""
    reg = ToolRegistry()

    async def snap(args, ctx):
        return ToolResult("", "snap", "captured 800x600",
                          attachments=[Attachment("s.png", "image/png", "QUJD")])

    reg.register("snap", ToolSchema("snap", "snap", {"type": "object", "properties": {}}), snap)
    results = await _run_one_tool(tmp_path, reg, "snap")
    assert results[0].data["content"] == "captured 800x600"
    assert "base64" not in results[0].data["content"]


def test_text_of_drops_image_blocks():
    """The SSE event is a transcript; a base64 PNG in every frame would dwarf
    it. The image still reaches the model through the message itself."""
    from vibe.runtime.langgraph import _text_of
    blocks = [{"type": "text", "text": "captured"},
              {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}]
    assert _text_of(blocks) == "captured"
    assert _text_of("plain") == "plain"


def test_is_error_reads_the_artifact():
    """This was hardcoded False, so a failing tool looked successful."""
    from langchain_core.messages import ToolMessage

    from vibe.runtime.langgraph import _is_error
    assert _is_error(ToolMessage(content="x", tool_call_id="c1", artifact={"is_error": True})) is True
    assert _is_error(ToolMessage(content="x", tool_call_id="c1", artifact={"is_error": False})) is False
    assert _is_error(ToolMessage(content="x", tool_call_id="c1")) is False


def test_to_lc_message_text_only():
    from vibe.runtime.langgraph import _to_lc_message
    m = Message(role="user", content="hi")
    lc = _to_lc_message(m)
    assert lc.type == "human"
    assert lc.content == "hi"
