# services/vibe/src/vibe/events.py
from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from vibe.auth import LOOPBACK_OWNER_ID

# A subscriber that falls this far behind is not reading anymore; its oldest
# events are dropped rather than growing the queue without bound.
_MAX_QUEUED_PER_SUBSCRIBER = 1000

# Bump when the events table shape changes; EventLog._open() applies the steps.
#   1 -> 2: index (session_id, type, seq) (BE-12/R3-T8).
#   2 -> 3: owner_id column + index (owner_id, session_id, seq) (R6-T1/L-1).
_SCHEMA_VERSION = 3

# How many times one append() re-seeds the session counter and retries when
# another allocator already stored the seq it picked. Bounded on purpose: an
# unbounded loop against a writer that never stops would hang the request, and
# the caller deserves a named failure rather than a stall (BE-21).
_INSERT_ATTEMPTS = 3


class EventSeqConflict(RuntimeError):
    """A durable event could not be given a seq above the stored maximum.

    Raised after `_INSERT_ATTEMPTS` collisions on the events primary key. It
    replaces the raw ``sqlite3.IntegrityError`` so a caller can tell "this one
    event could not be numbered" apart from a genuine storage failure, and so a
    duplicate-seq append never reaches the route as an IntegrityError.
    """

    def __init__(self, session_id: str, attempts: int) -> None:
        super().__init__(
            f"could not allocate an event seq for session {session_id}"
            f" after {attempts} attempt(s)"
        )
        self.session_id = session_id
        self.attempts = attempts


def _is_duplicate_seq(error: sqlite3.IntegrityError) -> bool:
    """True when the violation is the events ``(session_id, seq)`` primary key.

    ``sqlite_errorname`` is exact; the message is the fallback for a SQLite
    build that does not expose it. Any other IntegrityError (a NULL, a missing
    column) is not a lost race and must not be retried away.
    """
    if getattr(error, "sqlite_errorname", "") == "SQLITE_CONSTRAINT_PRIMARYKEY":
        return True
    return "events.session_id, events.seq" in str(error)


@dataclass
class Event:
    session_id: str
    seq: int
    type: str
    payload: dict[str, Any]


@runtime_checkable
class EventStore(Protocol):
    """The durable-event surface every consumer actually depends on.

    `EventLog` is the implementation (sqlite, or in-memory when constructed
    without a path). The protocol exists so callers name the *capability* rather
    than the class: a different backing store can drop in without touching
    `UsageTracker`, `SessionLifecycle`, the runtime context or the routes, and
    a test can substitute a fake without building a database.
    """

    def next_seq(self, session_id: str) -> int: ...

    async def append(self, session_id: str, type: str, payload: dict[str, Any]) -> int: ...

    async def get(self, session_id: str, after_seq: int = 0) -> list[Event]: ...

    def last_seq(self, session_id: str) -> int: ...

    def clear(self, session_id: str) -> None: ...

    def close(self) -> None: ...


class EventLog:
    """Append-only event log, in memory or backed by SQLite.

    `db_path=None` keeps the log in memory (tests, throwaway runs). With a path,
    durable events survive a restart — the log used to live in a plain dict, so
    every conversation vanished on restart while the session rows in sqlite
    survived, leaving the sidebar full of sessions that each opened empty.

    Writes go through a worker thread under a lock: sqlite is blocking, and
    doing it inline would stall the event loop and every SSE stream with it.
    """

    def __init__(self, db_path: Path | str | None = None):
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None
        self._events: dict[str, list[Event]] = {}
        self._seq: dict[str, int] = {}
        if db_path is not None:
            self._db = self._open(Path(db_path))

    @staticmethod
    def _open(path: Path) -> sqlite3.Connection:
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        # WAL lets readers and a writer proceed concurrently; NORMAL is safe
        # there (the only durability lost is the last commit on a power cut).
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=5000")
        # Applied step by step so an existing database is *migrated*, not
        # recreated: the version in the file decides what is still missing.
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            con.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                " session_id TEXT NOT NULL,"
                " seq INTEGER NOT NULL,"
                " type TEXT NOT NULL,"
                " payload TEXT NOT NULL,"
                " PRIMARY KEY (session_id, seq))"
            )
        if version < 2:
            # Message paging and UsageTracker read one session's events of one
            # type. Without this index the planner can only use the primary
            # key's (session_id, seq) autoindex and must filter the type in
            # Python; at 25 local sessions that is invisible. Splitting the
            # store protocol so those calls push the filter into SQL is real
            # work with a real compatibility cost, so it stays deferred -- this
            # is the index that work would need, and nothing else (BE-12).
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_session_type_seq"
                " ON events (session_id, type, seq)"
            )
        if version < 3:
            EventLog._add_owner_column(con)
        if version < _SCHEMA_VERSION:
            con.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            con.commit()
        return con

    @staticmethod
    def _add_owner_column(con: sqlite3.Connection) -> None:
        """Step v3: every event row names its owner, and is indexed by it.

        The events table is keyed by (session_id, seq) and a session id is a
        globally unique uuid, so today a read cannot cross owners: the owner
        filter would be redundant. The column is still recorded now because
        adding it later means rewriting every existing row once the log is
        large, while adding it here costs one defaulted column, and the index is
        the one owner-scoped reads would need if session ids ever stop being
        globally unique.

        ADD COLUMN has no IF NOT EXISTS, so the column list is checked first --
        a re-run after a crash between the ALTER and the version bump must be a
        no-op rather than an error.
        """
        columns = {row["name"] for row in con.execute("PRAGMA table_info(events)")}
        if "owner_id" not in columns:
            con.execute(
                "ALTER TABLE events ADD COLUMN owner_id TEXT NOT NULL"
                f" DEFAULT '{LOOPBACK_OWNER_ID}'"
            )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_owner_session_seq"
            " ON events (owner_id, session_id, seq)"
        )

    def _max_seq(self, session_id: str) -> int:
        """Highest seq already recorded for a session (0 if none).

        Ephemeral events (text chunks, turn boundaries) reserve a seq without
        being stored, so after a restart the counter resumes from the last
        *durable* seq. Reusing those few numbers is harmless: a restart also
        ends every in-flight run, so no client is mid-turn to resume from.
        """
        if self._db is None:
            return 0
        row = self._db.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM events WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row[0])

    def next_seq(self, session_id: str) -> int:
        """Reserve the next sequence number without storing an event.

        Ephemeral events (streaming text chunks, turn boundaries) still need a
        monotonic seq: the client's resume cursor is the last seq it saw, so a
        zero seq there made every reconnect replay the session from the start.
        They are deliberately not stored — the durable record of a turn is
        assistant/message, and one log row per token would bloat the log.
        """
        with self._lock:
            if session_id not in self._seq:
                self._seq[session_id] = self._max_seq(session_id)
            seq = self._seq[session_id] + 1
            self._seq[session_id] = seq
            return seq

    async def append(self, session_id: str, type: str, payload: dict[str, Any]) -> int:
        seq = self.next_seq(session_id)
        event = Event(session_id=session_id, seq=seq, type=type, payload=payload)
        if self._db is None:
            self._events.setdefault(session_id, []).append(event)
            return seq
        # `_insert` renumbers the event if another allocator already stored its
        # seq, so the seq returned here is the one actually recorded.
        await asyncio.to_thread(self._insert, event)
        return event.seq

    def _insert(self, event: Event) -> None:
        # default=str: a payload that is not JSON-native degrades to a string
        # instead of taking the whole request down with it.
        #
        # The seq came from an in-memory counter that can be stale: a second
        # EventLog, or a restarted process overlapping this one, may have stored
        # that number already. Losing that race used to take the whole request
        # down with a bare sqlite3.IntegrityError, so the insert re-seeds from
        # the durable maximum and retries a bounded number of times (BE-21).
        with self._lock:
            for attempt in range(1, _INSERT_ATTEMPTS + 1):
                try:
                    self._db.execute(
                        "INSERT INTO events (session_id, seq, type, payload, owner_id)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (event.session_id, event.seq, event.type,
                         json.dumps(event.payload, default=str), LOOPBACK_OWNER_ID),
                    )
                    self._db.commit()
                    return
                except sqlite3.IntegrityError as error:
                    if not _is_duplicate_seq(error):
                        raise
                    if attempt == _INSERT_ATTEMPTS:
                        raise EventSeqConflict(event.session_id, attempt) from error
                    # Take a fresh number above the durable maximum, under the
                    # same lock. `max` keeps the counter from dropping below a
                    # seq already streamed to a client, so a number the client
                    # has seen is never handed out again.
                    self._seq[event.session_id] = max(
                        self._seq.get(event.session_id, 0), self._max_seq(event.session_id)
                    )
                    event.seq = self._seq[event.session_id] + 1
                    self._seq[event.session_id] = event.seq

    async def get(self, session_id: str, after_seq: int = 0) -> list[Event]:
        if self._db is None:
            return [e for e in self._events.get(session_id, []) if e.seq > after_seq]
        return await asyncio.to_thread(self._select, session_id, after_seq)

    def _select(self, session_id: str, after_seq: int) -> list[Event]:
        with self._lock:
            rows = self._db.execute(
                "SELECT seq, type, payload FROM events"
                " WHERE session_id = ? AND seq > ? ORDER BY seq",
                (session_id, after_seq),
            ).fetchall()
        return [
            Event(session_id=session_id, seq=int(r[0]), type=r[1], payload=json.loads(r[2]))
            for r in rows
        ]

    def last_seq(self, session_id: str) -> int:
        with self._lock:
            if session_id not in self._seq:
                self._seq[session_id] = self._max_seq(session_id)
            return self._seq[session_id]

    def clear(self, session_id: str) -> None:
        """Drop every event for a session. Used by the delete cascade."""
        with self._lock:
            self._seq.pop(session_id, None)
            self._events.pop(session_id, None)
            if self._db is not None:
                self._db.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
                self._db.commit()

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None


class Subscription:
    """One subscriber's private event queue.

    Registered eagerly on construction so an event published immediately after
    subscribing cannot fall into the gap before the first read.
    """

    def __init__(self, bus: EventBus, session_id: str, queue: asyncio.Queue[Event]):
        self._bus = bus
        self._session_id = session_id
        self._queue = queue
        self._closed = False

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> Event:
        if self._closed:
            raise StopAsyncIteration
        return await self._queue.get()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bus._discard(self._session_id, self._queue)

    def pending(self) -> list[Event]:
        """Events queued but not yet consumed (tests and diagnostics)."""
        out: list[Event] = []
        while not self._queue.empty():
            out.append(self._queue.get_nowait())
        return out


class EventBus:
    """Fan-out pub/sub: every subscriber receives every event.

    A single shared queue per session made subscribers compete for events —
    two tabs, or a reconnecting client overlapping its predecessor, each got a
    random subset of the stream (and an event dequeued by a subscriber that was
    being cancelled was dropped outright). Each subscriber now owns a queue.
    """

    def __init__(self):
        self._subscribers: dict[str, set[asyncio.Queue[Event]]] = {}

    @property
    def subscriber_count(self) -> int:
        return sum(len(queues) for queues in self._subscribers.values())

    def _discard(self, session_id: str, queue: asyncio.Queue[Event]) -> None:
        queues = self._subscribers.get(session_id)
        if queues is None:
            return
        queues.discard(queue)
        if not queues:
            self._subscribers.pop(session_id, None)

    async def publish(self, session_id: str, event: Event) -> None:
        for queue in list(self._subscribers.get(session_id, ())):
            if queue.qsize() >= _MAX_QUEUED_PER_SUBSCRIBER:
                # Racy by definition: another consumer may have drained it.
                with contextlib.suppress(asyncio.QueueEmpty):  # pragma: no cover
                    queue.get_nowait()
            queue.put_nowait(event)

    def subscribe(self, session_id: str) -> Subscription:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.setdefault(session_id, set()).add(queue)
        return Subscription(self, session_id, queue)

    async def stream(self, session_id: str) -> AsyncIterator[Event]:
        """Convenience async iterator that cleans up on exit."""
        subscription = self.subscribe(session_id)
        try:
            async for event in subscription:
                yield event
        finally:
            await subscription.aclose()
