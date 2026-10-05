# tests/test_container.py
import dataclasses

import pytest

from vibe.approvals import ApprovalStore
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventBus, EventLog
from vibe.lifecycle import SessionLifecycle
from vibe.models import ModelRef
from vibe.runs import RunRegistry
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.services.messages import MessageService
from vibe.services.sessions import SessionService
from vibe.store import SessionStore
from vibe.tools.registry import ToolRegistry
from vibe.usage.tracker import UsageTracker


def _settings(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    return Settings(workspace_dir=ws, port=8000)


def test_build_composes_every_seam(tmp_path):
    c = Container.build(_settings(tmp_path))
    assert isinstance(c.store, SessionStore)
    assert isinstance(c.event_log, EventLog)
    assert isinstance(c.event_bus, EventBus)
    assert isinstance(c.tool_registry, ToolRegistry)
    assert isinstance(c.runtime, LangGraphRuntime)
    assert isinstance(c.usage, UsageTracker)
    assert isinstance(c.approval_store, ApprovalStore)
    assert isinstance(c.runs, RunRegistry)
    assert isinstance(c.lifecycle, SessionLifecycle)
    assert isinstance(c.session_service, SessionService)
    assert isinstance(c.message_service, MessageService)
    assert c.executors == {}
    assert c.autorun_policies == {}


def test_container_is_frozen(tmp_path):
    """A seam is swapped by replacing the container, never by assigning a field."""
    c = Container.build(_settings(tmp_path))
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.store = None


def test_unknown_override_is_rejected(tmp_path):
    """A typo in an override must not look like a passing test.

    Silently ignoring a misspelled name would leave the real store in place and
    the test would exercise production code while believing it used the stub.
    """
    with pytest.raises(TypeError, match="unknown container override"):
        Container.build(_settings(tmp_path), storee=None)


def test_per_session_executor_is_stable_and_overridable(tmp_path):
    c = Container.build(_settings(tmp_path))
    ws = tmp_path / "ws" / "s1"
    ws.mkdir(parents=True)
    assert c.get_executor("s1", ws) is c.get_executor("s1", ws)

    sentinel = object()
    overridden = Container.build(_settings(tmp_path), get_executor=lambda sid, workspace: sentinel)
    assert overridden.get_executor("s1", ws) is sentinel


@pytest.mark.asyncio
async def test_an_overridden_store_is_the_one_the_lifecycle_cascades_through(tmp_path):
    """The reason overrides are applied before anything derives from them.

    The lifecycle captures its collaborators by reference. Patching app.state
    after construction left it holding the real store, so a test that deleted
    a session cascaded through production code.
    """
    store = SessionStore(db_path=tmp_path / "test.db")
    log = EventLog()
    c = Container.build(_settings(tmp_path), store=store, event_log=log)
    sid = await store.create_session(ModelRef("openai", "gpt-4o"))

    await c.lifecycle.delete(sid)

    assert await store.get_session(sid) is None
    assert await log.get(sid) == []
    # The default store on disk was never created, let alone written to.
    assert not (tmp_path / "ws" / "sessions.db").exists()
