# tests/test_migrations.py
"""R6-T1 (L-1) and R6-T8 (L-8): owner_id on every persisted row.

The owner column is the one change in this program that touches data the user
already has on disk, so these tests do not assert against a fresh database: they
build a real pre-migration file, put real rows in it, and then open it with the
current code. A migration that only works on an empty database would pass a
weaker test and lose the user's sessions on the upgrade that matters.

Running the migration twice is also asserted. SQLite has no ADD COLUMN IF NOT
EXISTS, so the column check is what makes a second open a no-op rather than an
error.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from vibe.auth import LOOPBACK_OWNER_ID
from vibe.events import EventLog
from vibe.models import ModelRef
from vibe.store import Session, SessionStore

_MODEL_JSON = '{"provider_id": "openai", "model_id": "gpt-4o"}'

#: The sessions table exactly as schema version 1 shipped it, without owner_id.
_OLD_SESSIONS = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    model_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_OLD_EVENTS = """
CREATE TABLE events (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (session_id, seq)
)
"""


def _old_sessions_db(path: Path, rows: list[tuple[str, str]]) -> None:
    """Write a version-1 sessions database with the given (id, title) rows."""
    con = sqlite3.connect(path)
    con.execute(_OLD_SESSIONS)
    for sid, title in rows:
        con.execute(
            "INSERT INTO sessions (id, title, model_ref, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (sid, title, _MODEL_JSON, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()


def _old_events_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(_OLD_EVENTS)
    con.execute(
        "INSERT INTO events (session_id, seq, type, payload) VALUES (?, ?, ?, ?)",
        ("old-session", 1, "user/message", '{"content": "hello"}'),
    )
    con.execute("PRAGMA user_version = 2")
    con.commit()
    con.close()


def _user_version(path: Path) -> int:
    con = sqlite3.connect(path)
    try:
        return int(con.execute("PRAGMA user_version").fetchone()[0])
    finally:
        con.close()


def _columns(path: Path, table: str) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


async def test_an_existing_sessions_database_gains_owner_id_without_losing_rows(
    tmp_path: Path,
) -> None:
    db = tmp_path / "sessions.db"
    _old_sessions_db(db, [("old1", "My old session"), ("old2", "Another one")])

    store = SessionStore(db_path=db)
    try:
        assert "owner_id" in _columns(db, "sessions")
        assert _user_version(db) >= 2
        # The loopback user still sees exactly what was there, with the new column
        # defaulted rather than NULL.
        sessions = await store.list_sessions()
        assert sorted(s.id for s in sessions) == ["old1", "old2"]
        assert all(s.owner_id == LOOPBACK_OWNER_ID for s in sessions)
        old = await store.get_session("old1")
        assert old is not None
        assert old.title == "My old session"
        assert old.model_ref == ModelRef("openai", "gpt-4o")
    finally:
        store.close()


async def test_the_sessions_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    _old_sessions_db(db, [("old1", "Kept")])

    first = SessionStore(db_path=db)
    try:
        version = _user_version(db)
    finally:
        first.close()
    # A second open must not raise and must not move the version or the data.
    second = SessionStore(db_path=db)
    try:
        assert _user_version(db) == version
        row = await second.get_session("old1")
        assert row is not None and row.title == "Kept"
    finally:
        second.close()


async def test_two_owners_do_not_see_each_others_sessions(tmp_path: Path) -> None:
    store = SessionStore(db_path=tmp_path / "sessions.db")
    try:
        alice = await store.create_session(ModelRef("openai", "gpt-4o"), owner_id="alice")
        bob = await store.create_session(ModelRef("openai", "gpt-4o"), owner_id="bob")

        assert [s.id for s in await store.list_sessions(owner_id="alice")] == [alice]
        assert [s.id for s in await store.list_sessions(owner_id="bob")] == [bob]
        assert await store.get_session(bob, owner_id="alice") is None
        assert await store.get_session(alice, owner_id="bob") is None
        assert await store.count_sessions(owner_id="alice") == 1

        # The local owner is a third, empty view: neither row leaks into it.
        assert await store.list_sessions() == []
    finally:
        store.close()


async def test_the_loopback_owner_is_the_default(tmp_path: Path) -> None:
    store = SessionStore(db_path=tmp_path / "sessions.db")
    try:
        sid = await store.create_session(ModelRef("openai", "gpt-4o"))
        row = await store.get_session(sid)
        assert row is not None and row.owner_id == LOOPBACK_OWNER_ID
        assert await store.get_session(sid, owner_id=LOOPBACK_OWNER_ID) is not None
        assert await store.list_sessions() != []
    finally:
        store.close()


async def test_a_second_owner_cannot_rename_or_delete_the_first_owners_session(
    tmp_path: Path,
) -> None:
    store = SessionStore(db_path=tmp_path / "sessions.db")
    try:
        alice = await store.create_session(ModelRef("openai", "gpt-4o"), owner_id="alice")
        await store.rename_session(alice, "stolen by bob", owner_id="bob")
        row = await store.get_session(alice, owner_id="alice")
        assert row is not None and row.title != "stolen by bob"
        await store.delete_session(alice, owner_id="bob")
        assert await store.get_session(alice, owner_id="alice") is not None
        await store.delete_session(alice, owner_id="alice")
        assert await store.get_session(alice, owner_id="alice") is None
    finally:
        store.close()


def test_a_session_row_defaults_to_the_loopback_owner() -> None:
    session = Session(id="s1", title="t", model_ref=ModelRef("openai", "gpt-4o"),
                      created_at="now", updated_at="now")
    assert session.owner_id == LOOPBACK_OWNER_ID


async def test_an_existing_events_database_gains_owner_id(tmp_path: Path) -> None:
    db = tmp_path / "events.db"
    _old_events_db(db)

    log = EventLog(db)
    try:
        assert "owner_id" in _columns(db, "events")
        assert _user_version(db) >= 3
        events = await log.get("old-session")
        assert [e.type for e in events] == ["user/message"]
        assert events[0].payload == {"content": "hello"}
        assert log.last_seq("old-session") == 1
    finally:
        log.close()


async def test_a_route_cannot_see_another_owners_session(client, container) -> None:
    """The owner filter is live through the API, not only inside the store.

    Loopback is the only owner that can authenticate, so a session belonging to
    someone else has to look like one that does not exist -- the same 404 the
    client already handles -- and must survive a rename, a delete and an abort
    aimed at it by the local owner.
    """
    alice = await container.store.create_session(
        ModelRef("openai", "gpt-4o"), owner_id="alice"
    )

    assert client.get(f"/sessions/{alice}").status_code == 404
    assert client.patch(f"/sessions/{alice}", json={"title": "stolen"}).status_code == 404
    assert client.get(f"/sessions/{alice}/files").status_code == 404
    assert client.post(f"/sessions/{alice}/abort").status_code == 404
    # Delete is deliberately idempotent (no 404), so the proof is that the row
    # is still there and still alice's afterwards.
    assert client.delete(f"/sessions/{alice}").status_code == 204

    survived = await container.store.get_session(alice, owner_id="alice")
    assert survived is not None and survived.title != "stolen"
    assert client.get("/sessions").json() == []

    # Control: the local owner still sees and can reach its own session.
    mine = await container.store.create_session(ModelRef("openai", "gpt-4o"))
    assert client.get(f"/sessions/{mine}").status_code == 200
    assert [s["id"] for s in client.get("/sessions").json()] == [mine]


async def test_the_events_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "events.db"
    _old_events_db(db)

    first = EventLog(db)
    first.close()
    version = _user_version(db)
    second = EventLog(db)
    try:
        assert _user_version(db) == version
        assert (await second.get("old-session"))[0].payload == {"content": "hello"}
    finally:
        second.close()
