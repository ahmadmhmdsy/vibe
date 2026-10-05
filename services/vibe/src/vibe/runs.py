# services/vibe/src/vibe/runs.py
"""Registry of in-flight agent runs, one per session.

The chat route streams a run to completion inside the POST. Without a handle
on that work there is nothing for an abort request to cancel — the frontend's
Stop button only flipped a local flag while the run kept going.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class RunHandle:
    session_id: str
    task: asyncio.Task | None = None
    aborted: bool = False
    _abort: asyncio.Event = field(default_factory=asyncio.Event)

    def request_abort(self) -> bool:
        """Cancel the run. True if a live run was actually stopped."""
        if self.aborted:
            return False
        self.aborted = True
        self._abort.set()
        if self.task is not None and not self.task.done():
            self.task.cancel()
            return True
        return False

    @property
    def abort_requested(self) -> bool:
        return self.aborted


class RunRegistry:
    def __init__(self):
        self._runs: dict[str, RunHandle] = {}

    def get(self, session_id: str) -> RunHandle | None:
        return self._runs.get(session_id)

    def is_running(self, session_id: str) -> bool:
        handle = self._runs.get(session_id)
        return handle is not None and not handle.aborted

    def start(self, session_id: str) -> RunHandle:
        handle = RunHandle(session_id=session_id)
        self._runs[session_id] = handle
        return handle

    def finish(self, session_id: str, handle: RunHandle) -> None:
        if self._runs.get(session_id) is handle:
            self._runs.pop(session_id, None)

    def abort(self, session_id: str) -> bool:
        handle = self._runs.get(session_id)
        if handle is None:
            return False
        return handle.request_abort()
