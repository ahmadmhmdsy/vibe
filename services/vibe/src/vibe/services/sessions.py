# services/vibe/src/vibe/services/sessions.py
"""Session and workspace operations.

This logic used to sit inside the route handlers, which meant the path-confinement
check could only be exercised by standing up a whole FastAPI app. It is a pure
function of the store, the lifecycle and the workspace root, so a test can now
call it directly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from vibe.auth import LOOPBACK_OWNER_ID
from vibe.lifecycle import SessionLifecycle
from vibe.models import ModelRef
from vibe.projects import EmptyWorkspaceSource, ProjectSource, remove_workspace
from vibe.store import SessionStore


class SessionService:
    """Everything a session owns beyond its sqlite row.

    Deleting a session is deliberately here rather than on the store: a session
    also owns a workspace directory, a dev-server subprocess, an executor, an
    autorun policy, its event log and any pending approvals. Deleting only the
    row left all of them behind (audit H3).
    """

    def __init__(
        self,
        store: SessionStore,
        lifecycle: SessionLifecycle,
        workspace_dir: Path,
        default_source: ProjectSource | None = None,
    ):
        self._store = store
        self._lifecycle = lifecycle
        self._workspace_dir = workspace_dir
        # What a session gets when the client asks for no particular source: the
        # empty workspace every session had before sources existed.
        self._default_source = default_source or EmptyWorkspaceSource()
        # The session's workspace is normally derivable from its id, so this is
        # only needed for an import that landed elsewhere -- and only until the
        # next read of the row, which is where `remember` gets its answer from.
        self._workspaces: dict[str, Path] = {}

    def workspace_path(self, sid: str) -> Path:
        """Where this session's files are.

        A persisted path when the session was imported in place, otherwise the
        default directory named after the id. Sync on purpose: this is called on
        the path-confined file-read/write hot path, and the answer was already
        read from the store by `require_session` on the way in.
        """
        return self._workspaces.get(sid) or (self._workspace_dir / sid)

    def remember(self, sid: str, workspace: str | Path | None) -> None:
        """Cache the workspace path a stored row carries.

        Called wherever a session row is read, so a process that restarts still
        resolves an imported session's files instead of an empty directory.
        """
        if workspace:
            self._workspaces[sid] = Path(workspace)

    def ensure_workspace(self, sid: str) -> Path:
        """Create the session workspace if needed and return its path."""
        ws = self.workspace_path(sid)
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def resolve_file(self, sid: str, relpath: str) -> Path | None:
        """Resolve a client-supplied path inside the session workspace.

        Returns None for anything that escapes the workspace, so a handler answers
        400/404 without re-implementing the check. A relpath with ".." in it is
        the common case this exists for.
        """
        ws = self.workspace_path(sid)
        p = (ws / relpath).resolve()
        if not p.is_relative_to(ws.resolve()):
            return None
        return p

    # Every call that reaches a stored row names its owner. The default keeps
    # the local single-user path and existing callers working, and each route
    # passes the authenticated owner explicitly so the value is never assumed.

    async def create(
        self,
        model_ref: ModelRef,
        owner_id: str = LOOPBACK_OWNER_ID,
        source: ProjectSource | None = None,
    ) -> str:
        """Create the session row, then materialize its project (M8/C1).

        The order is forced: the destination offered to a source is named after
        the session id, so the row has to exist before there is somewhere to
        materialize into. That makes rolling the row back this method's job when
        a source refuses -- a bad folder or an unreachable repository must leave
        no half-created session behind for the sidebar to show.

        `materialize` is blocking (mkdir, file writes, `git clone`), so it runs
        in a worker thread: it must not stall the event loop and every other
        session's stream with it.
        """
        sid = await self._store.create_session(model_ref, owner_id)
        dest = self._workspace_dir / sid
        try:
            layout = await asyncio.to_thread((source or self._default_source).materialize, dest)
        except Exception:
            await self._store.delete_session(sid, owner_id)
            # Only ever `dest`, which this method just named: an imported folder
            # is a path the source chose, never one to clean up.
            remove_workspace(dest)
            raise
        if layout.path != dest:
            await self._store.set_workspace_path(sid, str(layout.path), owner_id)
        self._workspaces[sid] = layout.path
        return sid

    async def list(self, owner_id: str = LOOPBACK_OWNER_ID) -> list:
        return await self._store.list_sessions(owner_id)

    async def rename(self, sid: str, title: str, owner_id: str = LOOPBACK_OWNER_ID) -> None:
        await self._store.rename_session(sid, title, owner_id)

    async def retitle_from_message(self, sid: str, text: str, owner_id: str = LOOPBACK_OWNER_ID) -> bool:
        """Title the session from a message, unless it was renamed by hand."""
        return await self._store.retitle_from_message(sid, text, owner_id)

    async def set_model(self, sid: str, model_ref: ModelRef, owner_id: str = LOOPBACK_OWNER_ID) -> None:
        await self._store.set_model(sid, model_ref, owner_id)

    async def delete(self, sid: str, owner_id: str = LOOPBACK_OWNER_ID) -> None:
        await self._lifecycle.delete(sid, owner_id)
        self._workspaces.pop(sid, None)

    def read_text(self, sid: str, relpath: str) -> str:
        p = self.resolve_file(sid, relpath)
        if p is None or not p.exists():
            raise FileNotFoundError(relpath)
        return p.read_text(encoding="utf-8")

    def write_text(self, sid: str, relpath: str, content: str) -> None:
        p = self.resolve_file(sid, relpath)
        if p is None:
            raise ValueError("path outside workspace")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
