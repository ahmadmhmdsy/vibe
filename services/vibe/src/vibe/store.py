# services/vibe/src/vibe/store.py
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from vibe.auth import LOOPBACK_OWNER_ID
from vibe.models import ModelRef

# Bump when the sessions table shape changes; _migrate() applies the steps.
# Stored in the database itself, so an existing install upgrades in place.
#
# v2 added owner_id: every row now names who it belongs to. The loopback app has
# exactly one owner, so the column is filled with that owner's id and every read
# filters on it -- which means a second owner can be added later without moving
# anyone's data or rewriting a query.
_SCHEMA_VERSION = 2

# A session created before its first message has nothing to show in the
# sidebar, so it gets a placeholder. The first user message replaces it (see
# SessionStore.retitle_from_message).
_UNTITLED_PREFIX = "Untitled "

# Long enough to recognise the request in the sidebar, short enough that a
# session row never wraps onto a second line.
_TITLE_MAX = 60

# The columns every read selects, so a new column is added in one place.
_COLUMNS = "id, title, model_ref, created_at, updated_at, owner_id"


def title_from_text(text: str) -> str:
    """Derive a session title from a message.

    Deliberately not an LLM call: a title is a navigation aid, and spending a
    model call — and waiting on it — to label a session would put latency on
    every first message for something the opening sentence already says.
    """
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""
    if len(collapsed) <= _TITLE_MAX:
        return collapsed
    return collapsed[: _TITLE_MAX - 1].rstrip() + "…"


def is_placeholder_title(title: str) -> bool:
    """True while the title is still the placeholder from creation."""
    return title.startswith(_UNTITLED_PREFIX)


@dataclass
class Session:
    id: str
    title: str
    model_ref: ModelRef
    created_at: str
    updated_at: str
    # Defaulted so the single local user never has to name it, and so a row
    # built by older test code still describes the same session.
    owner_id: str = LOOPBACK_OWNER_ID


class SessionStore:
    """SQLite-backed session index.

    Every method is async but sqlite is blocking, so each body runs in a worker
    thread under a lock. Done inline, a slow query would stall the whole event
    loop — and with it every SSE stream, not just the request that asked.

    Every method takes the owner and filters on it. The parameter defaults to
    the loopback owner, so a caller that has no principal (a test, a script, the
    local app) keeps working, while a caller that has one cannot accidentally
    read a session that belongs to someone else.
    """

    def __init__(self, db_path: str | Path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # WAL lets a reader and a writer proceed concurrently; NORMAL is safe
        # there (only the last commit is at risk on a power cut, not the file).
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._migrate()

    def _migrate(self) -> None:
        """Bring the file up to _SCHEMA_VERSION, in place and only once.

        Each step is guarded by the version it introduces, so an existing
        install upgrades without losing rows and a current one does no work.
        """
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        if version >= _SCHEMA_VERSION:
            return
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model_ref TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        if version < 2:
            self._add_owner_column()
        self._db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        self._db.commit()

    def _add_owner_column(self) -> None:
        """Step v2: give every existing row an owner without rewriting it.

        ADD COLUMN is the only way to change a table in place, and SQLite has no
        IF NOT EXISTS for it, so the column list is checked first: a database
        that already has the column (a re-run, or a crash between the ALTER and
        the version bump) must not raise. The default is the loopback owner,
        which is who owns every row that exists before this change.
        """
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(sessions)")}
        if "owner_id" not in columns:
            self._db.execute(
                "ALTER TABLE sessions ADD COLUMN owner_id TEXT NOT NULL"
                f" DEFAULT '{LOOPBACK_OWNER_ID}'"
            )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_owner_updated"
            " ON sessions (owner_id, updated_at DESC)"
        )

    async def create_session(
        self, model_ref: ModelRef, owner_id: str = LOOPBACK_OWNER_ID
    ) -> str:
        return await asyncio.to_thread(self._create_session, model_ref, owner_id)

    def _create_session(self, model_ref: ModelRef, owner_id: str) -> str:
        import uuid

        sid = uuid.uuid4().hex[:12]
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._db.execute(
                "INSERT INTO sessions (id, title, model_ref, created_at, updated_at, owner_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                # A title is a placeholder until the first message arrives and
                # can be summarised; see the audit's missing-implementation list.
                (sid, f"Untitled {sid[:4]}",
                 json.dumps({"provider_id": model_ref.provider_id, "model_id": model_ref.model_id}),
                 now, now, owner_id),
            )
            self._db.commit()
        return sid

    async def get_session(
        self, session_id: str, owner_id: str = LOOPBACK_OWNER_ID
    ) -> Session | None:
        return await asyncio.to_thread(self._get_session, session_id, owner_id)

    def _get_session(self, session_id: str, owner_id: str) -> Session | None:
        with self._lock:
            row = self._db.execute(
                f"SELECT {_COLUMNS} FROM sessions WHERE id = ? AND owner_id = ?",
                (session_id, owner_id),
            ).fetchone()
        if row is None:
            return None
        return self._session_from_row(row)

    async def list_sessions(self, owner_id: str = LOOPBACK_OWNER_ID) -> list[Session]:
        return await asyncio.to_thread(self._list_sessions, owner_id)

    def _list_sessions(self, owner_id: str) -> list[Session]:
        with self._lock:
            rows = self._db.execute(
                f"SELECT {_COLUMNS} FROM sessions WHERE owner_id = ?"
                " ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return [self._session_from_row(r) for r in rows]

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            title=row["title"],
            model_ref=ModelRef(**json.loads(row["model_ref"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            owner_id=row["owner_id"],
        )

    async def rename_session(
        self, session_id: str, title: str, owner_id: str = LOOPBACK_OWNER_ID
    ) -> None:
        await asyncio.to_thread(self._touch, session_id, owner_id, title=title)

    async def retitle_from_message(
        self, session_id: str, text: str, owner_id: str = LOOPBACK_OWNER_ID
    ) -> bool:
        """Title a session from one of its messages. True if it did.

        Only fires while the title is still the placeholder, so a title the user
        renamed by hand is never clobbered by a later message.
        """
        return await asyncio.to_thread(self._retitle_from_message, session_id, text, owner_id)

    def _retitle_from_message(self, session_id: str, text: str, owner_id: str) -> bool:
        title = title_from_text(text)
        if not title:
            return False
        with self._lock:
            row = self._db.execute(
                "SELECT title FROM sessions WHERE id = ? AND owner_id = ?",
                (session_id, owner_id),
            ).fetchone()
            if row is None or not is_placeholder_title(row["title"]):
                return False
            now = datetime.now(UTC).isoformat()
            self._db.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                (title, now, session_id, owner_id),
            )
            self._db.commit()
        return True

    async def set_model(
        self, session_id: str, model_ref: ModelRef, owner_id: str = LOOPBACK_OWNER_ID
    ) -> None:
        await asyncio.to_thread(self._touch, session_id, owner_id, model_ref=model_ref)

    def _touch(self, session_id: str, owner_id: str, title: str | None = None,
               model_ref: ModelRef | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            if title is not None:
                self._db.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                    (title, now, session_id, owner_id),
                )
            if model_ref is not None:
                self._db.execute(
                    "UPDATE sessions SET model_ref = ?, updated_at = ? WHERE id = ? AND owner_id = ?",
                    (json.dumps({"provider_id": model_ref.provider_id,
                                "model_id": model_ref.model_id}), now, session_id, owner_id),
                )
            self._db.commit()

    async def delete_session(
        self, session_id: str, owner_id: str = LOOPBACK_OWNER_ID
    ) -> None:
        await asyncio.to_thread(self._delete_session, session_id, owner_id)

    def _delete_session(self, session_id: str, owner_id: str) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM sessions WHERE id = ? AND owner_id = ?",
                (session_id, owner_id),
            )
            self._db.commit()

    async def count_sessions(self, owner_id: str = LOOPBACK_OWNER_ID) -> int:
        return await asyncio.to_thread(self._count_sessions, owner_id)

    def _count_sessions(self, owner_id: str) -> int:
        with self._lock:
            return int(
                self._db.execute(
                    "SELECT COUNT(*) FROM sessions WHERE owner_id = ?", (owner_id,)
                ).fetchone()[0]
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()
