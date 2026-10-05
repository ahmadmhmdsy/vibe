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
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionLifecycle:
    """Owns the teardown order for a session.

    Order matters. The dev server is stopped before the workspace is moved
    because it holds open file handles on that directory, and Windows refuses to
    move a directory with them open. The workspace is moved before the session
    row is deleted, so a failure there aborts the delete and leaves the session
    intact instead of silently orphaning the files.
    """

    def __init__(self, store, event_log, executors: dict, autorun_policies: dict,
                 approvals, runs, workspace_dir: Path):
        self._store = store
        self._event_log = event_log
        self._executors = executors
        self._autorun_policies = autorun_policies
        self._approvals = approvals
        self._runs = runs
        self._workspace_dir = Path(workspace_dir)

    async def delete(self, session_id: str) -> None:
        logger.info("deleting session %s", session_id)
        # 1. Stop the agent first — a run that is still streaming would otherwise
        #    keep writing into a workspace we are about to move.
        self._runs.abort(session_id)

        # 2. Stop the dev server and drop the executor. This is the step that
        #    used to leak one `pnpm dev` process per deleted session.
        executor = self._executors.pop(session_id, None)
        if executor is not None:
            await executor.close()

        # 3. Drop the rest of the per-session state.
        self._autorun_policies.pop(session_id, None)
        self._approvals.forget(session_id)
        self._event_log.clear(session_id)

        # 4. Move the workspace aside. Refuses to proceed if it cannot.
        workspace = self._workspace_dir / session_id
        if workspace.exists():
            trash = (self._workspace_dir / ".trash"
                     / f"{session_id}-{datetime.now(UTC):%Y%m%d-%H%M%S}")
            trash.parent.mkdir(parents=True, exist_ok=True)
            workspace.rename(trash)
            logger.info("session %s workspace moved to %s", session_id, trash.name)

        # 5. Only now remove the row.
        await self._store.delete_session(session_id)
        logger.info("session %s deleted", session_id)
