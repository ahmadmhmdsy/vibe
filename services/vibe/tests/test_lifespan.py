# tests/test_lifespan.py
"""Startup reconciliation and shutdown cleanup (R5-T6)."""

import asyncio
from contextlib import suppress

import httpx
import pytest

from vibe.api.app import create_app, reconcile_open_turns
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventLog
from vibe.models import ModelRef
from vibe.store import SessionStore


class FakeExecutor:
    """Stands in for a session's dev server and records being stopped."""

    def __init__(self) -> None:
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1


class FakeServer:
    """The slice of uvicorn.Server that /admin/shutdown touches."""

    def __init__(self) -> None:
        self.should_exit = False


def make_settings(tmp_path) -> Settings:
    return Settings(workspace_dir=tmp_path / "ws", mode="dev")


async def seed(tmp_path, settings: Settings, *events: tuple[str, dict]) -> str:
    """Write a session and its events the way a previous run would have."""
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    store = SessionStore(settings.workspace_dir / "sessions.db")
    log = EventLog(settings.workspace_dir / "events.db")
    try:
        sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
        for type_, payload in events:
            await log.append(sid, type_, payload)
    finally:
        store.close()
        log.close()
    return sid


@pytest.mark.asyncio
async def test_a_turn_left_open_by_a_crash_is_closed_at_startup(tmp_path):
    settings = make_settings(tmp_path)
    sid = await seed(tmp_path, settings, ("user/message", {"content": "hi"}))
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        events = await app.state.container.event_log.get(sid)

    assert [e.type for e in events] == ["user/message", "turn/aborted"]
    assert "reason" in events[-1].payload


@pytest.mark.asyncio
async def test_a_crash_after_a_tool_call_is_also_closed(tmp_path):
    """The tail that matters is the last *stored* event, not the last streamed one."""
    settings = make_settings(tmp_path)
    sid = await seed(
        tmp_path,
        settings,
        ("user/message", {"content": "build it"}),
        ("tool_call", {"name": "write_file"}),
        ("tool_result", {"ok": True}),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        events = await app.state.container.event_log.get(sid)
    assert [e.type for e in events][-1] == "turn/aborted"


@pytest.mark.asyncio
async def test_a_finished_turn_is_left_alone(tmp_path):
    """Reconciliation must not rewrite history: an answered turn stays answered."""
    settings = make_settings(tmp_path)
    sid = await seed(
        tmp_path,
        settings,
        ("user/message", {"content": "hi"}),
        ("assistant/message", {"content": "hello"}),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        events = await app.state.container.event_log.get(sid)
    assert [e.type for e in events] == ["user/message", "assistant/message"]


@pytest.mark.asyncio
async def test_a_session_with_no_events_is_not_flagged(tmp_path):
    settings = make_settings(tmp_path)
    sid = await seed(tmp_path, settings)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert await app.state.container.event_log.get(sid) == []


@pytest.mark.asyncio
async def test_shutdown_stops_dev_servers_and_cancels_in_flight_runs(tmp_path):
    settings = make_settings(tmp_path)
    container = Container.build(settings)
    fake = FakeExecutor()
    container.executors["s1"] = fake  # type: ignore[index]
    handle = container.runs.start("s1")
    handle.task = asyncio.create_task(asyncio.sleep(30))

    app = create_app(settings, container=container)
    async with app.router.lifespan_context(app):
        assert fake.closed == 0
        assert handle.abort_requested is False

    assert fake.closed == 1, "shutdown must stop the dev server a session started"
    assert handle.abort_requested is True, "shutdown must cancel the run, not orphan it"
    with suppress(asyncio.CancelledError):
        await handle.task


@pytest.mark.asyncio
async def test_admin_shutdown_asks_the_server_to_stop(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    app.state.uvicorn_server = FakeServer()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 51000)),
        base_url="http://localhost",
    ) as client:
        resp = await client.post("/admin/shutdown")
        assert resp.status_code == 200
        assert resp.json() == {"status": "shutting_down", "stopping": True}
        # GET would be reachable from any page the browser loads, and
        # OriginGuard only guards state-changing methods.
        assert (await client.get("/admin/shutdown")).status_code == 405

    assert app.state.uvicorn_server.should_exit is True
    assert app.state.shutdown_requested is True


@pytest.mark.asyncio
async def test_admin_shutdown_refuses_a_non_loopback_caller(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings)
    app.state.uvicorn_server = FakeServer()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("203.0.113.5", 51000)),
        base_url="http://localhost",
    ) as client:
        resp = await client.post("/admin/shutdown")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"
    assert app.state.uvicorn_server.should_exit is False


@pytest.mark.asyncio
async def test_reconcile_is_idempotent(tmp_path):
    settings = make_settings(tmp_path)
    await seed(tmp_path, settings, ("user/message", {"content": "hi"}))
    store = SessionStore(settings.workspace_dir / "sessions.db")
    log = EventLog(settings.workspace_dir / "events.db")
    try:
        assert await reconcile_open_turns(store, log) == 1
        assert await reconcile_open_turns(store, log) == 0
    finally:
        store.close()
        log.close()


@pytest.mark.asyncio
async def test_startup_reaps_dev_servers_left_by_a_previous_run(tmp_path, monkeypatch):
    """R5-T9 wiring: startup hands the reaper the workspace root's pidfile.

    The reap itself is test_orphans.py's subject; what is asserted here is that
    a crashed run's dev servers are looked at all, because until this call site
    existed nothing ever reaped them and the ports stayed taken (AC-9).
    """
    import vibe.api.app as app_module
    from vibe.maintenance import ReapReport

    settings = make_settings(tmp_path)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    seen: list[object] = []

    def fake_reap(root: object) -> ReapReport:
        seen.append(root)
        return ReapReport()

    monkeypatch.setattr(app_module, "reap_dev_servers", fake_reap)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        pass
    assert seen == [settings.workspace_dir], "startup must reap orphans in the workspace root"


@pytest.mark.asyncio
async def test_a_failing_reap_does_not_stop_startup(tmp_path, monkeypatch):
    """Housekeeping must never be the reason the app cannot start."""
    import vibe.api.app as app_module

    settings = make_settings(tmp_path)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)

    def boom(root: object) -> None:
        raise RuntimeError("pidfile unreadable")

    monkeypatch.setattr(app_module, "reap_dev_servers", boom)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert app.state.container.settings is settings
