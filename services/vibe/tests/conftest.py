# tests/conftest.py

import asyncio
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


class CountingRuntime:
    """Streams one chunk and counts how many runs actually started.

    The count is the point: a guard that lets two concurrent sends through
    shows up as calls == 2, not as a status code the test has to guess at.
    """

    def __init__(self, delay: float = 0.05):
        self.calls = 0
        self._delay = delay

    async def run(self, input, ctx):
        self.calls += 1
        await asyncio.sleep(self._delay)
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


class RecordingRuntime:
    """Records the messages handed to the model on every run."""

    def __init__(self):
        self.inputs: list = []

    async def run(self, input, ctx):
        self.inputs.append(list(input.messages))
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


@pytest.fixture
def container(app):
    return app.state.container


@pytest.fixture
def event_log(container):
    return container.event_log


@pytest.fixture
def lifecycle(container):
    return container.lifecycle


@pytest.fixture
def counting_runtime():
    return CountingRuntime()


@pytest.fixture
def recording_runtime():
    return RecordingRuntime()


@pytest.fixture
def store_path(container):
    """The provider store's file, inside the tmp workspace."""
    return container.settings.workspace_dir / "providers.json"


@pytest.fixture
def store(container):
    return container.custom_provider_store


@pytest.fixture
def session_id(client):
    """Create a session through the real route and return its id."""
    resp = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]
