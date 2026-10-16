# services/vibe/tests/test_e2e.py

import pytest
from fastapi.testclient import TestClient

from vibe.api.app import create_app
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventBus, EventLog
from vibe.models import AgentEvent
from vibe.store import SessionStore
from vibe.tools.executor_tools import register_executor_tools
from vibe.tools.files import register_file_tools
from vibe.tools.registry import ToolRegistry


class E2ERuntime:
    async def run(self, input, ctx):
        # write a minimal app file
        (ctx.workspace_path / "src").mkdir(parents=True, exist_ok=True)
        (ctx.workspace_path / "src" / "App.tsx").write_text(
            "export default function App(){ return <div>Hello Vibe</div> }"
        )
        yield AgentEvent(kind="text_chunk", data={"text": "created App.tsx"})
        yield AgentEvent(kind="turn_complete", data={})


class NoOpAutorun:
    async def maybe_run(self, ctx, changed_files):
        pass


@pytest.mark.asyncio
async def test_e2e_core_loop(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    registry = ToolRegistry()
    register_file_tools(registry)
    register_executor_tools(registry)
    container = Container.build(
        settings,
        store=SessionStore(db_path=tmp_path / "test.db"),
        event_log=EventLog(),
        event_bus=EventBus(),
        runtime=E2ERuntime(),
        tool_registry=registry,
        # The factory seam takes the owner as a keyword; the stub mirrors the
        # real signature so a change to it breaks here rather than at runtime.
        get_autorun=lambda sid, ws, *, owner_id=LOOPBACK_OWNER_ID: NoOpAutorun(),
    )
    client = TestClient(create_app(settings, container=container))
    # create session
    sid = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
    # send message
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "build a hello world app"})
    assert resp.status_code == 200
    assert "created App.tsx" in resp.json()["content"]
    # verify file was written
    assert (tmp_path / "ws" / sid / "src" / "App.tsx").exists()
