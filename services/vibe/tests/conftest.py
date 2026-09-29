# tests/conftest.py
import pytest
from pathlib import Path
from vibe.api.app import create_app
from vibe.config import Settings
from vibe.store import SessionStore
from vibe.events import EventLog, EventBus
from vibe.tools.registry import ToolRegistry
from vibe.tools.files import register_file_tools
from vibe.runtime.base import AgentContext
from vibe.models import AgentEvent

class StubRuntime:
    async def run(self, input, ctx):
        yield AgentEvent(kind="text_chunk", data={"text": "hello from agent"})
        yield AgentEvent(kind="turn_complete", data={})

class StubExecutor:
    def __init__(self):
        self._dev_server = None

    @property
    def dev_server_url(self):
        return self._dev_server.url if self._dev_server else None

    async def install(self, packages):
        from vibe.models import ToolResult
        return ToolResult("", "install", "ok")
    async def build(self):
        from vibe.models import ToolResult
        return ToolResult("", "build", "ok")
    async def start_dev_server(self):
        from vibe.executor.base import DevServerHandle
        self._dev_server = DevServerHandle(port=5173, url="http://127.0.0.1:5173/", process=None)
        return self._dev_server
    async def stop_dev_server(self):
        self._dev_server = None
    async def read_console_logs(self, tail): return ""
    async def screenshot(self): return b""

@pytest.fixture
def app(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    app = create_app(settings)
    app.state.store = SessionStore(db_path=tmp_path / "test.db")
    app.state.event_log = EventLog()
    app.state.event_bus = EventBus()
    app.state.runtime = StubRuntime()
    reg = ToolRegistry()
    register_file_tools(reg)
    app.state.tool_registry = reg
    app.state.executor = StubExecutor()
    return app

@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)
