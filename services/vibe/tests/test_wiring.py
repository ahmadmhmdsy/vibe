# tests/test_wiring.py
# Regression protection for the create_app factory wiring (Task 16).
# Asserts each seam is composed with the correct type, the per-session
# registries are stable, and the provider registry builds real langchain models.
from vibe.api.app import create_app
from vibe.autorun.policy import AutoRunPolicy
from vibe.config import Settings
from vibe.events import EventBus, EventLog
from vibe.executor.local import LocalSubprocessExecutor
from vibe.models import ModelRef
from vibe.providers.registry import build_llm_factory
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.store import SessionStore
from vibe.tools.registry import ToolRegistry
from vibe.usage.tracker import UsageTracker


def test_create_app_composes_all_seams(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    app = create_app(settings)
    assert isinstance(app.state.container.store, SessionStore)
    assert isinstance(app.state.container.event_log, EventLog)
    assert isinstance(app.state.container.event_bus, EventBus)
    assert isinstance(app.state.container.tool_registry, ToolRegistry)
    assert isinstance(app.state.container.runtime, LangGraphRuntime)
    assert isinstance(app.state.container.usage, UsageTracker)


def test_per_session_executor_is_stable(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    app = create_app(settings)
    ws = tmp_path / "ws" / "s1"
    ws.mkdir(parents=True, exist_ok=True)
    ex1 = app.state.container.get_executor("s1", ws)
    ex2 = app.state.container.get_executor("s1", ws)
    assert ex1 is ex2
    assert isinstance(ex1, LocalSubprocessExecutor)


def test_per_session_autorun_is_stable(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    app = create_app(settings)
    ws = tmp_path / "ws" / "s1"
    ws.mkdir(parents=True, exist_ok=True)
    ar1 = app.state.container.get_autorun("s1", ws)
    ar2 = app.state.container.get_autorun("s1", ws)
    assert ar1 is ar2
    assert isinstance(ar1, AutoRunPolicy)


def test_llm_factory_builds_real_models(tmp_path):
    settings = Settings(
        workspace_dir=tmp_path / "ws",
        port=8000,
        openai_api_key="sk-test",
        anthropic_api_key="sk-test",
        opencode_api_key="sk-test",
    )
    factory = build_llm_factory(settings, custom_store=None)
    for provider in ("openai", "anthropic", "opencode-go"):
        model = factory(ModelRef(provider_id=provider, model_id="test"))
        assert hasattr(model, "bind_tools")
        assert hasattr(model, "astream")
