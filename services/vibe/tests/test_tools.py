# tests/test_tools.py
import pytest
from vibe.tools.registry import ToolRegistry
from vibe.tools.files import register_file_tools
from vibe.models import ToolResult
from vibe.runtime.base import AgentContext
from vibe.events import EventBus
from vibe.store import SessionStore
from pathlib import Path

@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=None,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    r = await reg.execute("write_file", {"path": "hello.txt", "content": "hi"}, ctx)
    assert r.is_error is False
    r2 = await reg.execute("read_file", {"path": "hello.txt"}, ctx)
    assert "hi" in r2.content

@pytest.mark.asyncio
async def test_write_file_rejects_path_outside_workspace(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=None,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    r = await reg.execute("write_file", {"path": "../escape.txt", "content": "x"}, ctx)
    assert r.is_error is True

@pytest.mark.asyncio
async def test_list_files(tmp_path):
    reg = ToolRegistry()
    register_file_tools(reg)
    (tmp_path / "a.txt").write_text("a")
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=None,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    r = await reg.execute("list_files", {}, ctx)
    assert "a.txt" in r.content
