# tests/test_autorun.py

import pytest

from vibe.autorun.policy import AutoRunPolicy
from vibe.events import EventBus
from vibe.models import AgentEvent
from vibe.runtime.base import AgentContext
from vibe.store import SessionStore


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
    @property
    def dev_server_url(self):
        return "http://127.0.0.1:5173/"

    async def start_dev_server(self):
        from vibe.executor.base import DevServerHandle
        return DevServerHandle(port=5173, url="http://127.0.0.1:5173/", process=None)
    async def stop_dev_server(self): pass
    # None: this executor has no browser driver, so there is no console to read.
    async def read_console_logs(self, url, tail=200, level="error"): return None
    async def screenshot(self, url): return None
    async def close(self): pass


class CleanBuildExecutor(FlakyExecutor):
    """Builds cleanly every time, with a console the test controls."""

    def __init__(self, logs):
        super().__init__()
        self._logs = logs

    async def build(self):
        from vibe.models import ToolResult

        self.build_count += 1
        return ToolResult("", "build", "build ok")

    async def read_console_logs(self, url, tail=200, level="error"):
        # Report it once: a fix that worked removes the error from the console.
        logs, self._logs = self._logs, None
        return logs

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
async def test_autorun_fixes_a_runtime_error_when_the_console_reports_one(tmp_path):
    ex = CleanBuildExecutor("Uncaught TypeError: x is not a function")
    rt = FixRuntime()
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    await policy.maybe_run(ctx, ["src/App.tsx"])
    assert rt.calls == 1


@pytest.mark.asyncio
async def test_autorun_does_not_claim_a_console_check_it_cannot_make(tmp_path):
    """No driver means no console was read. Treating that as "clean" would let
    the loop report a check that never happened (audit M6)."""
    ex = CleanBuildExecutor(None)
    rt = FixRuntime()
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    ctx = AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))
    await policy.maybe_run(ctx, ["src/App.tsx"])
    assert rt.calls == 0
    assert ex.build_count == 1


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
