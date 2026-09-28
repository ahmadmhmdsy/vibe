# services/vibe/src/vibe/store.py
from __future__ import annotations
import sqlite3, uuid, json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from vibe.models import ModelRef

@dataclass
class Session:
    id: str
    title: str
    model_ref: ModelRef
    created_at: str
    updated_at: str

class SessionStore:
    def __init__(self, db_path: Path):
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model_ref TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        self._db.commit()

    async def create_session(self, model_ref: ModelRef) -> str:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        title = f"Untitled {sid[:4]}"
        self._db.execute(
            "INSERT INTO sessions (id, title, model_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (sid, title, json.dumps({"provider_id": model_ref.provider_id, "model_id": model_ref.model_id}), now, now),
        )
        self._db.commit()
        return sid

    async def list_sessions(self) -> list[Session]:
        rows = self._db.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
        return [self._to_session(r) for r in rows]

    async def get_session(self, session_id: str) -> Session | None:
        r = self._db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return self._to_session(r) if r else None

    async def rename_session(self, session_id: str, title: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._db.execute("UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?", (title, now, session_id))
        self._db.commit()

    async def delete_session(self, session_id: str) -> None:
        self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._db.commit()

    def _to_session(self, r: sqlite3.Row) -> Session:
        mr = json.loads(r["model_ref"])
        return Session(
            id=r["id"], title=r["title"],
            model_ref=ModelRef(provider_id=mr["provider_id"], model_id=mr["model_id"]),
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
