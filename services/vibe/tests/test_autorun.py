# tests/test_autorun.py
import pytest
from vibe.autorun.policy import AutoRunPolicy
from vibe.runtime.base import AgentContext
from vibe.events import EventBus
from vibe.store import SessionStore
from vibe.models import AgentEvent
from pathlib import Path

class FlakyExecutor:
    def __init__(self): self.build_count = 0
    async def install(self, packages):
        from vibe.models import ToolResult
        return ToolResult("", "install", "ok")
    async def build(self):
        from vibe.models import ToolResult
        self.build_count += 1
        if self.build_count == 1:
            return ToolResult("", "build", "error: cannot find module './App'", True)
        return ToolResult("", "build", "build ok")
    async def start_dev_server(self):
        from vibe.executor.base import DevServerHandle
        return DevServerHandle(port=5173, url="http://127.0.0.1:5173/", process=None)
    async def stop_dev_server(self): pass
    async def read_console_logs(self, tail): return ""
    async def screenshot(self): return b""

class FixRuntime:
    def __init__(self): self.calls = 0
    async def run(self, input, ctx):
        self.calls += 1
        yield AgentEvent(kind="text_chunk", data={"text": "fixing"})
        yield AgentEvent(kind="turn_complete", data={})

@pytest.mark.asyncio
async def test_autorun_fixes_build_error(tmp_path):
    ex = FlakyExecutor()
    rt = FixRuntime()
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    await policy.maybe_run(ctx, ["src/App.tsx"])
    assert ex.build_count == 2  # first build failed, fix turn, second build passed
    assert rt.calls == 1  # one fix turn

@pytest.mark.asyncio
async def test_autorun_skips_when_no_changes(tmp_path):
    ex = FlakyExecutor()
    rt = FixRuntime()
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    await policy.maybe_run(ctx, [])
    assert ex.build_count == 0
    assert rt.calls == 0
