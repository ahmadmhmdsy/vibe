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


class ScriptedFixRuntime:
    """Streams a scripted turn, and keeps the input it was handed.

    FixRuntime above yields a text chunk and is enough to count calls; this one
    lets a test assert what the loop *did* with the events.
    """

    def __init__(self, script):
        self.script = script
        self.inputs = []

    async def run(self, input, ctx):
        self.inputs.append(input)
        for event in self.script:
            yield event


class RecordingBus(EventBus):
    """An EventBus that keeps the type of everything published to it."""

    def __init__(self):
        super().__init__()
        self.published = []

    async def publish(self, session_id, event):
        self.published.append(event.type)
        await super().publish(session_id, event)


def _fix_ctx(tmp_path, ex, bus, log, **extra):
    return AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                        event_bus=bus, store=SessionStore(db_path=tmp_path / "t.db"),
                        event_log=log, **extra)


@pytest.mark.asyncio
async def test_fix_turn_events_reach_the_log_and_the_bus(tmp_path):
    """BE-08: a fix turn used to be consumed and thrown away.

    Its tool calls and its prose existed nowhere the user could see, and the
    prompt that started it was missing from the transcript too — while
    "model-visible means logged" is the rule everywhere else.
    """
    from vibe.events import EventLog

    ex = FlakyExecutor()  # the first build fails, so exactly one fix turn runs
    rt = ScriptedFixRuntime([
        AgentEvent(kind="tool_call", data={"tool_call": {"name": "write_file"}}),
        AgentEvent(kind="text_chunk", data={"text": "fixing the build"}),
        AgentEvent(kind="turn_complete", data={}),
    ])
    log = EventLog()
    bus = RecordingBus()
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    await policy.maybe_run(_fix_ctx(tmp_path, ex, bus, log), ["src/App.tsx"])

    events = await log.get("s1")
    types = [e.type for e in events]
    assert "tool_call" in types, "a fix turn must be logged like any other turn"
    assert "user/message" in types, "the prompt the model saw must be in the transcript"
    assert any(e.type == "assistant/message" and "fixing the build" in e.payload["content"]
               for e in events), types
    # The bus is what a connected client is streaming: logging without publishing
    # would leave the UI showing a turn it never heard about.
    assert bus.published.count("tool_call") == 1
    assert "turn_complete" in bus.published
    assert "assistant/message" in bus.published


@pytest.mark.asyncio
async def test_fix_turn_carries_the_system_prompt(tmp_path):
    """The fix loop is the same agent, so it gets the same standing instructions."""
    from vibe.events import EventLog
    from vibe.prompts import DEFAULT_SYSTEM_PROMPT

    ex = FlakyExecutor()
    rt = ScriptedFixRuntime([AgentEvent(kind="turn_complete", data={})])
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    await policy.maybe_run(_fix_ctx(tmp_path, ex, EventBus(), EventLog()), ["src/App.tsx"])
    assert rt.inputs[0].system == DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_autorun_stops_between_iterations_when_the_user_pressed_stop(tmp_path):
    """Stop has to stop the fix loop, not only the chat turn that preceded it."""
    from vibe.events import EventLog

    ex = FlakyExecutor()
    rt = ScriptedFixRuntime([AgentEvent(kind="turn_complete", data={})])
    policy = AutoRunPolicy(executor=ex, runtime=rt, max_fix_iterations=3)
    ctx = _fix_ctx(tmp_path, ex, EventBus(), EventLog(), is_aborted=lambda: True)
    await policy.maybe_run(ctx, ["src/App.tsx"])
    assert ex.build_count == 0, "a stopped turn must not even start a build"
    assert rt.inputs == []

