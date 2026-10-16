# tests/test_event_store.py
"""R3-T8 (BE-12): index the event log now, defer the store-level query split.

`MessageService.page` and `UsageTracker._records` project a session's whole log
per request. At today's sizes that is invisible, and rewriting the store protocol
for it would be speculative work; the cheap honest step is the index the deferred
session+type queries would need, applied through the existing user_version
migration without touching the protocol.
"""

import sqlite3

import pytest

from vibe.events import _SCHEMA_VERSION, EventLog

INDEX = "idx_events_session_type_seq"


def _query_plan(db_path, sql, params=()) -> str:
    con = sqlite3.connect(db_path)
    try:
        return " ".join(str(row[3]) for row in con.execute("EXPLAIN QUERY PLAN " + sql, params))
    finally:
        con.close()


def _seed_v1(db_path, rows=(("s1", 1, "user/message", '{"content": "hi"}'),)) -> None:
    """A database written before the index existed."""
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE events (session_id TEXT NOT NULL, seq INTEGER NOT NULL,"
        " type TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY (session_id, seq))"
    )
    con.executemany("INSERT INTO events VALUES (?, ?, ?, ?)", rows)
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()


# --- a fresh database -------------------------------------------------------


def test_a_fresh_log_creates_the_session_type_index(tmp_path):
    EventLog(tmp_path / "events.db").close()
    con = sqlite3.connect(tmp_path / "events.db")
    try:
        names = {row[1] for row in con.execute("PRAGMA index_list(events)")}
    finally:
        con.close()
    assert INDEX in names


def test_the_deferred_session_and_type_query_uses_the_index(tmp_path):
    """The shape R6-T9 would run: one session, one event type, in seq order."""
    EventLog(tmp_path / "events.db").close()
    plan = _query_plan(
        tmp_path / "events.db",
        "SELECT seq, type, payload FROM events WHERE session_id = ? AND type = ? ORDER BY seq",
        ("s1", "usage"),
    )
    assert INDEX in plan, plan


def test_an_existing_v1_database_is_migrated_in_place(tmp_path):
    db = tmp_path / "events.db"
    _seed_v1(db)

    EventLog(db).close()

    con = sqlite3.connect(db)
    try:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        names = {row[1] for row in con.execute("PRAGMA index_list(events)")}
        rows = con.execute("SELECT session_id, seq, type, payload FROM events").fetchall()
    finally:
        con.close()
    assert version == _SCHEMA_VERSION
    assert INDEX in names
    assert rows == [("s1", 1, "user/message", '{"content": "hi"}')], "a migration must not lose events"


@pytest.mark.asyncio
async def test_a_migrated_log_still_reads_its_events(tmp_path):
    db = tmp_path / "events.db"
    _seed_v1(
        db,
        (
            ("s1", 1, "user/message", '{"content": "hi"}'),
            ("s1", 3, "usage", '{"provider": "openai"}'),
            ("s2", 1, "user/message", '{"content": "other"}'),
        ),
    )

    log = EventLog(db)
    try:
        events = await log.get("s1")
        assert [(e.seq, e.type) for e in events] == [(1, "user/message"), (3, "usage")]
    finally:
        log.close()


def test_the_migration_is_idempotent(tmp_path):
    db = tmp_path / "events.db"
    EventLog(db).close()
    EventLog(db).close()  # opening a current database must not fail or duplicate
    con = sqlite3.connect(db)
    try:
        assert con.execute("PRAGMA user_version").fetchone()[0] == _SCHEMA_VERSION
        assert (
            con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?", (INDEX,)).fetchone()[0] == 1
        )
    finally:
        con.close()
