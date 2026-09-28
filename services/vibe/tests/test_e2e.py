# services/vibe/tests/test_e2e.py
import pytest
from fastapi.testclient import TestClient
from vibe.api.app import create_app
from vibe.config import Settings
from vibe.store import SessionStore
from vibe.events import EventLog, EventBus
from vibe.tools.registry import ToolRegistry
from vibe.tools.files import register_file_tools
from vibe.tools.executor_tools import register_executor_tools
from vibe.runtime.base import AgentContext
from vibe.models import AgentEvent
from pathlib import Path

class E2ERuntime:
    async def run(self, input, ctx):
        # write a minimal app file
        from vibe.models import ToolResult
        (ctx.workspace_path / "src").mkdir(parents=True, exist_ok=True)
        (ctx.workspace_path / "src" / "App.tsx").write_text(
            "export default function App(){ return <div>Hello Vibe</div> }")
        yield AgentEvent(kind="text_chunk", data={"text": "created App.tsx"})
        yield AgentEvent(kind="turn_complete", data={})

@pytest.mark.asyncio
async def test_e2e_core_loop(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    app = create_app(settings)
    app.state.store = SessionStore(db_path=tmp_path / "test.db")
    app.state.event_log = EventLog()
    app.state.event_bus = EventBus()
    app.state.runtime = E2ERuntime()
    reg = ToolRegistry()
    register_file_tools(reg)
    register_executor_tools(reg)
    app.state.tool_registry = reg
    from fastapi.testclient import TestClient
    client = TestClient(app)
    # create session
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # send message
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "build a hello world app"})
    assert resp.status_code == 200
    assert "created App.tsx" in resp.json()["content"]
    # verify file was written
    assert (tmp_path / "ws" / sid / "src" / "App.tsx").exists()
