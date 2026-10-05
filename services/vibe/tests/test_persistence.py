# tests/test_persistence.py
"""Persistence and portability guarantees added by the 2026-10-04 P0/P1 pass.

Covers the three ways data used to be lost or misplaced: an event log that lived
only in a dict, a workspace root that was never expanded, and a session index
that could be opened by two threads at once.
"""
import asyncio
from pathlib import Path

import pytest

from vibe.config import Settings
from vibe.events import EventBus, EventLog
from vibe.models import ModelRef
from vibe.store import SessionStore


class _QueryParams:
    def get(self, key, default=None):
        return default


class _Request:
    """Just enough of a FastAPI Request for the SSE route."""

    def __init__(self, app, query_params=None):
        self.app = app
        self.query_params = query_params or _QueryParams()


# --- Settings: the workspace root must be absolute and expanded ---------------


def test_workspace_dir_is_expanded_and_resolved():
    s = Settings(workspace_dir="~/vibe-workspaces")
    assert s.workspace_dir == Path.home() / "vibe-workspaces"
    assert s.workspace_dir.is_absolute()


def test_workspace_dir_defaults_to_the_home_directory():
    assert Settings().workspace_dir == Path.home() / "vibe-workspaces"


def test_host_defaults_to_loopback():
    assert Settings().host == "127.0.0.1"
    assert Settings(host="0.0.0.0").host == "0.0.0.0"


# --- EventLog: durable across a restart ---------------------------------------


@pytest.mark.asyncio
async def test_events_survive_a_restart(tmp_path):
    db = tmp_path / "events.db"
    log = EventLog(db)
    await log.append("s1", "user/message", {"content": "hello"})
    await log.append("s1", "assistant/message", {"content": "hi there"})
    log.close()

    # A brand-new instance over the same file is what a restart looks like.
    reopened = EventLog(db)
    events = await reopened.get("s1")
    assert [e.type for e in events] == ["user/message", "assistant/message"]
    assert events[0].payload == {"content": "hello"}
    assert [e.seq for e in events] == [1, 2]
    reopened.close()


@pytest.mark.asyncio
async def test_seq_resumes_from_the_last_durable_event(tmp_path):
    log = EventLog(tmp_path / "events.db")
    await log.append("s1", "user/message", {"content": "a"})
    log.close()

    reopened = EventLog(tmp_path / "events.db")
    assert reopened.last_seq("s1") == 1
    # The next durable event continues rather than restarting at 1.
    assert await reopened.append("s1", "assistant/message", {"content": "b"}) == 2
    reopened.close()


@pytest.mark.asyncio
async def test_in_memory_log_still_works():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "a"})
    assert [e.type for e in await log.get("s1")] == ["user/message"]
    assert await log.get("s1", after_seq=1) == []


@pytest.mark.asyncio
async def test_clear_drops_every_event_for_one_session_only(tmp_path):
    log = EventLog(tmp_path / "events.db")
    await log.append("s1", "user/message", {"content": "a"})
    await log.append("s2", "user/message", {"content": "b"})
    log.clear("s1")

    assert await log.get("s1") == []
    assert [e.payload["content"] for e in await log.get("s2")] == ["b"]
    log.close()


@pytest.mark.asyncio
async def test_a_non_json_payload_degrades_instead_of_raising(tmp_path):
    log = EventLog(tmp_path / "events.db")
    marker = object()
    # Used to raise sqlite3.ProgrammingError and take the request down with it.
    await log.append("s1", "tool/result", {"value": marker})
    (event,) = await log.get("s1")
    assert isinstance(event.payload["value"], str)
    log.close()


def test_events_table_is_in_wal_mode(tmp_path):
    log = EventLog(tmp_path / "events.db")
    mode = log._db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    log.close()


# --- SessionStore: concurrency and migrations ---------------------------------


@pytest.mark.asyncio
async def test_sessions_table_is_in_wal_mode(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    mode = store._db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    store.close()


@pytest.mark.asyncio
async def test_schema_version_is_recorded(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    assert store._db.execute("PRAGMA user_version").fetchone()[0] == 1
    store.close()


@pytest.mark.asyncio
async def test_an_existing_database_is_not_recreated(tmp_path):
    """Reopening must keep the rows, not recreate an empty table."""
    store = SessionStore(tmp_path / "sessions.db")
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    store.close()

    reopened = SessionStore(tmp_path / "sessions.db")
    assert await reopened.count_sessions() == 1
    assert (await reopened.get_session(sid)).id == sid
    reopened.close()


@pytest.mark.asyncio
async def test_concurrent_writes_do_not_corrupt_the_database(tmp_path):
    """Two coroutines inserting at once used to race on one connection."""
    store = SessionStore(tmp_path / "sessions.db")
    await asyncio.gather(
        *(store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
          for _ in range(20))
    )
    assert await store.count_sessions() == 20
    store.close()


@pytest.mark.asyncio
async def test_delete_removes_the_row(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    await store.delete_session(sid)
    assert await store.get_session(sid) is None
    store.close()


# --- The endpoint must replay from the durable log (audit H1) ------------------


@pytest.mark.asyncio
async def test_history_is_replayed_from_sqlite(tmp_path):
    # The SSE route must serve events from the durable log, not from memory.
    # This is the H1 fix end to end: the log is sqlite-backed, so a session's
    # history is still there after the process restarts. TestClient cannot read
    # an infinite SSE stream, so the route is driven directly (the pattern the
    # rest of the SSE suite uses).
    from vibe.api.routes.sessions import events

    class _Store:
        async def get_session(self, sid):
            return {"id": sid}

    class _App:
        class state:
            event_log = EventLog(tmp_path / "events.db")
            event_bus = EventBus()
            store = _Store()

    log = _App.state.event_log
    await log.append("s1", "user/message", {"content": "hello"})
    await log.append("s1", "assistant/message", {"content": "hi"})

    resp = await events("s1", _Request(_App()), _App().state)
    received = []

    async def consume():
        async for chunk in resp.body_iterator:
            received.append(chunk)
            if len(received) >= 2:
                return

    task = asyncio.create_task(consume())
    await asyncio.wait_for(task, timeout=2.0)

    assert any("hello" in c for c in received)
    assert any("hi" in c for c in received)
    log.close()
