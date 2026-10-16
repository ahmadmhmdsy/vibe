# tests/test_tools.py

import pytest

from vibe.events import EventBus
from vibe.models import Attachment, ToolResult, ToolSchema
from vibe.runtime.base import AgentContext
from vibe.store import SessionStore
from vibe.tools.files import register_file_tools
from vibe.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    r = await reg.execute("write_file", {"path": "hello.txt", "content": "hi"}, ctx)
    assert r.is_error is False
    r2 = await reg.execute("read_file", {"path": "hello.txt"}, ctx)
    assert "hi" in r2.content


@pytest.mark.asyncio
async def test_write_file_rejects_path_outside_workspace(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    r = await reg.execute("write_file", {"path": "../escape.txt", "content": "x"}, ctx)
    assert r.is_error is True


@pytest.mark.asyncio
async def test_list_files(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    (tmp_path / "a.txt").write_text("a")
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    r = await reg.execute("list_files", {}, ctx)
    assert "a.txt" in r.content


@pytest.mark.asyncio
async def test_to_langchain_tools(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    tools = reg.to_langchain_tools(ctx)
    assert len(tools) == 4


@pytest.mark.asyncio
async def test_write_file_rejects_sibling_prefix(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    sibling = tmp_path.parent / (tmp_path.name + "-evil")
    sibling.mkdir(exist_ok=True)
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    r = await reg.execute("write_file", {"path": f"../{tmp_path.name}-evil/secret.txt", "content": "x"}, ctx)
    assert r.is_error is True


@pytest.mark.asyncio
async def test_write_file_utf8(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )
    r = await reg.execute("write_file", {"path": "u.txt", "content": "日本語"}, ctx)
    assert r.is_error is False
    r2 = await reg.execute("read_file", {"path": "u.txt"}, ctx)
    assert "日本語" in r2.content


def _ctx(tmp_path):
    return AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=None,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )


@pytest.mark.asyncio
async def test_tool_payload_sends_content_not_the_dataclass(tmp_path):
    """LangChain stringifies whatever a tool returns, so a tool that returned
    its ToolResult handed the model `ToolResult(tool_call_id=..., content=...)`
    -- a Python repr -- instead of the output. Regression test for that."""
    reg = ToolRegistry()
    register_file_tools(reg)
    (tmp_path / "a.txt").write_text("hello")
    tools = {t.name: t for t in reg.to_langchain_tools(_ctx(tmp_path))}
    content = await tools["read_file"].ainvoke({"path": "a.txt"})
    assert isinstance(content, str)
    assert "hello" in content
    assert "ToolResult(" not in content


def test_tool_payload_reports_a_failure_in_the_artifact():
    """is_error used to be dropped on the floor, so a failing tool looked like
    a successful one to the model and to the UI."""
    from vibe.tools.registry import _payload

    _, artifact = _payload(ToolResult("", "t", "nope", is_error=True))
    assert artifact["is_error"] is True
    assert artifact["attachments"] == 0


@pytest.mark.asyncio
async def test_tool_payload_turns_attachments_into_image_blocks(tmp_path):
    """A screenshot has to reach the model as an image, not as a byte count."""
    reg = ToolRegistry()

    async def snap(args, ctx):
        return ToolResult("", "snap", "captured 800x600", attachments=[Attachment("s.png", "image/png", "QUJD")])

    reg.register("snap", ToolSchema("snap", "snap", {"type": "object", "properties": {}}), snap)
    tools = {t.name: t for t in reg.to_langchain_tools(_ctx(tmp_path))}
    content = await tools["snap"].ainvoke({})
    assert content[0] == {"type": "text", "text": "captured 800x600"}
    assert content[1]["image_url"]["url"] == "data:image/png;base64,QUJD"
