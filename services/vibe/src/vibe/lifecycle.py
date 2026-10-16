# services/vibe/src/vibe/lifecycle.py
"""Session lifecycle — what happens to everything a session owns when it ends.

Deleting a session used to remove a single sqlite row and nothing else: the
workspace directory, the dev-server subprocess, the executor, the autorun
policy, the event log, any pending approval and the usage records all
survived. A deleted session therefore kept its files on disk and kept a
`pnpm dev` process running, and the in-memory registries grew without bound.

The workspace is moved aside rather than deleted outright: deletion is
user-initiated and irreversible, so it goes to a `.trash` directory inside the
workspace root where it can be recovered.

The trash is not kept forever: `sweep_trash` drops entries older than
`trash_retention_days`, so a mistake stays recoverable for a bounded window
instead of every deleted `node_modules` staying on disk for good.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vibe.auth import LOOPBACK_OWNER_ID
from vibe.runs import SessionKey

logger = logging.getLogger(__name__)

#: The only names this sweep may remove. Our own delete path writes
#: `<session_id>-<YYYYMMDD-HHMMSS>`; a session id is `uuid4().hex[:12]`
#: (store.py), so it is exactly twelve lowercase hex characters. Anything else
#: under .trash belongs to the user and must survive (BE-11).
_TRASH_NAME = re.compile(r"^[0-9a-f]{12}-\d{8}-\d{6}$")

#: How long to keep trying to move a workspace aside. A dev server we just asked
#: to stop is usually still releasing its handles for a moment -- measured at
#: ~0.6 s for a vite tree after a real tree kill, and longer on a loaded machine
#: -- so the window covers the whole bounded shutdown the executor allows itself,
#: not just the first instant. It costs nothing when the move succeeds at once,
#: and an editor the user left open never lets go, which is why this still ends
#: in a named error rather than waiting forever. 25 x 0.2 s = 5 s.
_TRASH_MOVE_ATTEMPTS = 25
_TRASH_MOVE_DELAY = 0.2


class WorkspaceBusyError(RuntimeError):
    """The session workspace is still held open by another process.

    Raised instead of letting the operating system's PermissionError escape as
    a bare 500: the caller can say which directory is stuck and that the session
    is still there, and the transcript and row are left intact to retry.
    """


async def move_workspace_to_trash(workspace: Path, trash: Path) -> None:
    """Move a workspace to its trash name, retrying while handles are released.

    Renaming a directory on Windows fails with WinError 5 while any process
    still holds a file inside it, and the process this delete just stopped may
    need a moment to let go. Retrying a few times covers that; a permanent
    holder (an editor, or a dev server that outlived its executor) becomes a
    WorkspaceBusyError naming the cause.
    """
    for attempt in range(1, _TRASH_MOVE_ATTEMPTS + 1):
        try:
            workspace.rename(trash)
        except OSError as exc:
            if attempt == _TRASH_MOVE_ATTEMPTS:
                reason = exc.strerror or exc.__class__.__name__
                raise WorkspaceBusyError(
                    f"could not move {workspace.name} aside: a file in it is "
                    f"still open in another program ({reason}). Close whatever "
                    "has the session's files open and delete it again."
                ) from exc
            await asyncio.sleep(_TRASH_MOVE_DELAY)
        else:
            logger.info("session %s workspace moved to %s", workspace.name, trash.name)
            return


class SessionLifecycle:
    """Owns the teardown order for a session.

    Order matters. The dev server is stopped before the workspace is moved
    because it holds open file handles on that directory, and Windows refuses to
    move a directory with them open. The workspace is moved before the session
    row is deleted, so a failure there aborts the delete and leaves the session
    intact instead of silently orphaning the files.
    """

    def __init__(
        self,
        store,
        event_log,
        executors: dict,
        autorun_policies: dict,
        approvals,
        runs,
        workspace_dir: Path,
        trash_retention_days: int = 14,
    ):
        self._store = store
        self._event_log = event_log
        self._executors = executors
        self._autorun_policies = autorun_policies
        self._approvals = approvals
        self._runs = runs
        self._workspace_dir = Path(workspace_dir)
        #: 0 disables the sweep entirely: deleted workspaces are then kept
        #: forever, which is the behaviour every install had before this.
        self._trash_retention_days = trash_retention_days

    async def sweep_trash(self) -> list[Path]:
        """Remove trash entries older than the retention window.

        Returns the removed paths. Deliberately strict about what it touches:
        only directories directly inside <workspace_dir>/.trash whose name
        matches our own delete-path naming. Everything else is someone else's
        data. A non-positive retention disables the sweep.
        """
        if self._trash_retention_days <= 0:
            logger.info("trash sweep disabled (retention=%s days); nothing removed", self._trash_retention_days)
            return []
        # The filesystem walk and rmtree are blocking; keep them off the loop.
        return await asyncio.to_thread(self._sweep_trash)

    def _sweep_trash(self) -> list[Path]:
        trash = self._workspace_dir / ".trash"
        if not trash.is_dir():
            return []
        # Age comes from the entry's mtime -- the filesystem's own record of when
        # the workspace stopped changing. The name is the ownership gate only,
        # so a directory we did not write is never a candidate at all.
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=self._trash_retention_days)
        removed: list[Path] = []
        for entry in sorted(trash.iterdir(), key=lambda p: p.name):
            if entry.is_symlink() or not entry.is_dir() or not _TRASH_NAME.match(entry.name):
                continue
            try:
                modified = datetime.fromtimestamp(entry.stat().st_mtime, UTC)
            except OSError:
                logger.warning("trash sweep: could not read %s; leaving it", entry.name, exc_info=True)
                continue
            if modified >= cutoff:
                continue
            age_days = (now - modified).total_seconds() / 86400
            try:
                shutil.rmtree(entry)
            except OSError:
                # A locked file is common on Windows (a preview or editor still
                # holds it). Report it and keep the rest of the sweep going.
                logger.warning("trash sweep: could not remove %s (%.1f days old)", entry.name, age_days, exc_info=True)
                continue
            logger.info("trash sweep: removed %s (%.1f days old)", entry.name, age_days)
            removed.append(entry)
        return removed

    async def _workspace_of(self, session_id: str, owner_id: str) -> Path:
        """Where this session's files are.

        Normally the directory named after the id, but an import in place
        remembers a path elsewhere (M8/C1) -- and a session whose row is already
        gone (an idempotent second delete) is the default again.
        """
        session = await self._store.get_session(session_id, owner_id)
        if session is not None and session.workspace_path:
            return Path(session.workspace_path)
        return self._workspace_dir / session_id

    async def delete(self, session_id: str, owner_id: str = LOOPBACK_OWNER_ID) -> None:
        """Delete one owner's session and everything it owned.

        Everything below is keyed by (owner, session). The workspace is the one
        piece that lives on disk rather than in a registry, so it is resolved
        through the store -- which is what lets an imported project be found,
        and recognised as not ours to remove.
        """
        logger.info("deleting session %s for owner %s", session_id, owner_id)
        key = SessionKey(owner_id=owner_id, session_id=session_id)
        # 1. Stop the agent first — a run that is still streaming would otherwise
        #    keep writing into a workspace we are about to move.
        self._runs.abort(session_id, owner_id=owner_id)

        # 2. Stop the dev server and drop the executor. This is the step that
        #    used to leak one dev-server process per deleted session.
        executor = self._executors.pop(key, None)
        if executor is not None:
            await executor.close()

        # 3. Drop the per-session registries.
        self._autorun_policies.pop(key, None)
        self._approvals.forget(session_id)

        # 4. Move the workspace aside first. It is the only step that can fail
        #    for environmental reasons (a locked file, a permission error, a
        #    cross-device rename), and everything after it destroys something --
        #    so if it raises, the transcript and the row are both still here to
        #    retry. Clearing the log first meant a failed move left an empty
        #    conversation whose files were still on disk.
        #
        #    Only workspaces this app owns are moved. An imported project lives
        #    where the user put it (M8/C1) and is theirs: deleting the session
        #    must close the conversation and leave their folder alone.
        workspace = await self._workspace_of(session_id, owner_id)
        if workspace.exists() and workspace.resolve().is_relative_to(self._workspace_dir.resolve()):
            trash = self._workspace_dir / ".trash" / f"{session_id}-{datetime.now(UTC):%Y%m%d-%H%M%S}"
            trash.parent.mkdir(parents=True, exist_ok=True)
            await move_workspace_to_trash(workspace, trash)
        elif workspace.exists():
            logger.info("session %s was imported in place; leaving %s untouched", session_id, workspace)

        # 5. Now the destructive steps.
        self._event_log.clear(session_id)
        await self._store.delete_session(session_id, owner_id)
        logger.info("session %s deleted", session_id)

        # 6. Bound the trash while we are here: this is where it grows. The
        #    session is already gone, so a sweep failure must not fail the
        #    delete; sweep_trash logs per entry and returns what it removed.
        try:
            await self.sweep_trash()
        except OSError:
            logger.warning("trash sweep after deleting %s failed", session_id, exc_info=True)
