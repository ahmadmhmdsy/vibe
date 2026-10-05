# tests/test_usage.py
import pytest

from vibe.autorun.policy import AutoRunPolicy
from vibe.events import EventBus, EventLog
from vibe.executor.base import Executor
from vibe.models import AgentInput, Message, ModelRef, ToolResult, UsageRecord
from vibe.runtime.base import AgentContext
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.store import SessionStore
from vibe.usage.tracker import UsageTracker


class StubLlmWithUsage:
    """Returns an AIMessage carrying usage_metadata."""
    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        from langchain_core.messages import AIMessage
        self.calls += 1
        return AIMessage(content="hello", usage_metadata={
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "input_token_details": {"cache_read": 20},
        })


class StubToolRegistry:
    def to_langchain_tools(self, ctx):
        return []


class StubExecutor(Executor):
    def __init__(self):
        self.builds = 0

    async def build(self):
        self.builds += 1
        return ToolResult("", "build", "")

    async def install(self, packages):
        return ToolResult("", "install", "")

    async def read_console_logs(self, url, tail: int = 50, level: str = "error"):
        return None

    async def screenshot(self, url):
        return None

    async def close(self):
        pass


def _ctx(tmp_path, ex, log, bus, usage):
    return AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=bus, store=SessionStore(db_path=tmp_path / "t.db"),
                       event_log=log, approval_store=None)


@pytest.mark.asyncio
async def test_runtime_records_usage(tmp_path):
    llm = StubLlmWithUsage()
    log = EventLog()
    bus = EventBus()
    usage = UsageTracker(log=log, bus=bus)
    runtime = LangGraphRuntime(llm_factory=lambda m, session_id=None: llm,
                              tool_registry=StubToolRegistry(), usage=usage)
    ctx = _ctx(tmp_path, None, log, bus, usage)
    inp = AgentInput(session_id="s1", messages=[Message(role="user", content="hi")],
                     model=ModelRef(provider_id="openai", model_id="gpt-4o"))
    async for _ in runtime.run(inp, ctx):
        pass
    total = await usage.session_total("s1")
    assert total.input_tokens == 100
    assert total.output_tokens == 50
    assert total.cached_tokens == 20
    assert total.total_tokens == 150
    assert total.cost_usd > 0


@pytest.mark.asyncio
async def test_autorun_stops_when_over_budget(tmp_path):
    log = EventLog()
    bus = EventBus()
    usage = UsageTracker(log=log, bus=bus)
    await usage.record("s1", UsageRecord(provider="openai", model="gpt-4o",
                                          input_tokens=1000, output_tokens=500,
                                          cached_tokens=0, cache_write_tokens=0,
                                          cache_hit=False, cache_hit_rate=0.0,
                                          total_tokens=1500, cost_usd=0.0))
    ex = StubExecutor()
    policy = AutoRunPolicy(executor=ex, runtime=None, max_fix_iterations=3,
                           usage=usage, session_token_budget=100)
    ctx = _ctx(tmp_path, ex, log, bus, usage)
    await policy.maybe_run(ctx, ["file.ts"])
    assert ex.builds == 0  # over budget → no build


@pytest.mark.asyncio
async def test_autorun_runs_when_under_budget(tmp_path):
    log = EventLog()
    bus = EventBus()
    usage = UsageTracker(log=log, bus=bus)
    ex = StubExecutor()
    policy = AutoRunPolicy(executor=ex, runtime=None, max_fix_iterations=3,
                           usage=usage, session_token_budget=10000)
    ctx = _ctx(tmp_path, ex, log, bus, usage)
    await policy.maybe_run(ctx, ["file.ts"])
    assert ex.builds > 0  # under budget → builds
