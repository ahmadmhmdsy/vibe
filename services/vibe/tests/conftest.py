# tests/conftest.py

from dataclasses import replace

import pytest

from vibe.api.app import create_app
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventBus, EventLog
from vibe.models import AgentEvent
from vibe.store import SessionStore
from vibe.tools.files import register_file_tools
from vibe.tools.registry import ToolRegistry


class StubRuntime:
    async def run(self, input, ctx):
        yield AgentEvent(kind="text_chunk", data={"text": "hello from agent"})
        yield AgentEvent(kind="turn_complete", data={})


def swap(app, **changes):
    """Replace container fields, and return the new container.

    The container is frozen, so a seam is swapped by replacing the whole thing
    rather than assigning a field. Routes read it per request via
    `app.state.container`, so the swap is visible to every later request.
    """
    app.state.container = replace(app.state.container, **changes)
    return app.state.container


@pytest.fixture
def app(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    registry = ToolRegistry()
    register_file_tools(registry)
    # The stubs are passed to the builder, not patched in afterwards: the
    # lifecycle captures its collaborators by reference, so patching app.state
    # after the fact left it pointing at the real store and a test that deleted
    # a session would cascade through production code.
    container = Container.build(
        settings,
        store=SessionStore(db_path=tmp_path / "test.db"),
        event_log=EventLog(),
        event_bus=EventBus(),
        runtime=StubRuntime(),
        tool_registry=registry,
    )
    return create_app(settings, container=container)


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)
