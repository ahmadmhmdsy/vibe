# services/vibe/src/vibe/approvals.py
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Approval:
    """A pending supply-chain approval (agent wants to install a package)."""

    id: str
    session_id: str
    packages: list[str]
    status: str = "pending"  # pending | approved | denied
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "packages": self.packages,
            "status": self.status,
            "created_at": self.created_at,
        }


class ApprovalStore:
    """In-memory pending-approval registry keyed by approval id.

    The install tool creates an approval, emits a chat event, and waits on
    the approval's event; the settings/chat UI resolves it via approve/deny.
    """

    def __init__(self):
        self._approvals: dict[str, Approval] = {}
        self._events: dict[str, asyncio.Event] = {}

    def create(self, session_id: str, packages: list[str]) -> Approval:
        aid = uuid.uuid4().hex[:12]
        a = Approval(id=aid, session_id=session_id, packages=list(packages))
        self._approvals[aid] = a
        self._events[aid] = asyncio.Event()
        return a

    def get(self, approval_id: str) -> Approval | None:
        return self._approvals.get(approval_id)

    def resolve(self, approval_id: str, approved: bool) -> None:
        a = self._approvals.get(approval_id)
        if a is None:
            return
        a.status = "approved" if approved else "denied"
        ev = self._events.get(approval_id)
        if ev:
            ev.set()

    async def wait(self, approval_id: str, timeout: float = 600.0) -> str:
        """Block until the approval is resolved or the timeout elapses (→ denied)."""
        a = self._approvals.get(approval_id)
        if a is None:
            return "denied"
        ev = self._events.get(approval_id)
        if ev is None:
            return a.status
        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        except TimeoutError:
            a.status = "denied"
            return "denied"
        return a.status

    def forget(self, session_id: str) -> None:
        """Drop every approval belonging to a session (session deletion)."""
        for aid in [a.id for a in self._approvals.values() if a.session_id == session_id]:
            self._approvals.pop(aid, None)
            self._events.pop(aid, None)

    def list(self, session_id: str) -> list[Approval]:
        return [a for a in self._approvals.values() if a.session_id == session_id]
