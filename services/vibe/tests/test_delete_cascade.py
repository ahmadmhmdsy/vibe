# tests/test_delete_cascade.py
"""R1-T3: a delete that cannot finish must not destroy what it cannot undo (BE-06).

delete() cleared the event log before moving the workspace. When the move failed
-- a locked file, a permission error, a cross-device rename -- the transcript was
already gone while the session row and the user's files stayed on disk (probe 7
measured 2 events becoming 0). This pins the ordering property, not delete()
itself: the only step that fails here is pinpointed by monkeypatching rename.
"""
from pathlib import Path

import pytest

from vibe import lifecycle as lifecycle_module
from vibe.lifecycle import WorkspaceBusyError


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """The retry is real; waiting 0.8s per test for it is not."""
    monkeypatch.setattr(lifecycle_module, "_TRASH_MOVE_DELAY", 0)


async def test_failed_move_keeps_events_and_row(container, event_log, lifecycle, session_id, monkeypatch):
    await event_log.append(session_id, "user/message", {"content": "keep me"})
    # The workspace must exist, or delete() skips the move entirely and the test
    # would pass without exercising the step it is about.
    workspace = container.settings.workspace_dir / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text("user work", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "rename", boom)

    # A locked workspace is a named condition now, not a bare PermissionError:
    # the caller can tell the user which directory is stuck. The ordering
    # property this test exists for is unchanged.
    with pytest.raises(WorkspaceBusyError) as caught:
        await lifecycle.delete(session_id)
    assert session_id in str(caught.value)
    assert "delete it again" in str(caught.value)

    assert len(await event_log.get(session_id)) == 1, "a failed delete destroyed the transcript"
    assert await container.store.get_session(session_id) is not None, "the row was removed anyway"
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "user work"


async def test_a_move_that_fails_once_is_retried(
    container, lifecycle, session_id, monkeypatch
):
    """The dev server delete() just stopped may still be releasing handles.

    Reproduced on Windows as WinError 5 from a live preview holding a file in
    the workspace, which used to surface as a 500 with the session still there.
    """
    workspace = container.settings.workspace_dir / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text("user work", encoding="utf-8")

    real_rename = Path.rename
    calls: list[int] = []

    def flaky(self, target):
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError(5, "Access is denied")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky)

    await lifecycle.delete(session_id)

    assert len(calls) == 2, "the move was not retried"
    assert await container.store.get_session(session_id) is None, "the row survived a successful delete"
    trash = list((container.settings.workspace_dir / ".trash").iterdir())
    assert len(trash) == 1 and trash[0].name.startswith(session_id), "the workspace was not kept"
    assert (trash[0] / "notes.txt").read_text(encoding="utf-8") == "user work"


async def test_a_release_inside_the_widened_window_is_waited_out(
    container, lifecycle, session_id, monkeypatch
):
    """The window exists for a stopped dev server that is still letting go.

    Measured on this machine: a real vite tree releases its workspace ~0.6 s
    after a tree kill -- inside the 5 s window, and far outside one attempt. The
    retry must therefore keep trying until the handle is gone, not give up after
    the first refusal.
    """
    workspace = container.settings.workspace_dir / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text("user work", encoding="utf-8")

    real_rename = Path.rename
    calls: list[int] = []

    def slow_release(self, target):
        if self.name != session_id:
            return real_rename(self, target)
        calls.append(1)
        if len(calls) <= 3:
            raise PermissionError(5, "Access is denied")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", slow_release)

    await lifecycle.delete(session_id)

    assert len(calls) == 4, "the move was not retried until the handle was released"
    assert await container.store.get_session(session_id) is None, "the row survived a successful delete"
    trash = list((container.settings.workspace_dir / ".trash").iterdir())
    assert len(trash) == 1 and (trash[0] / "notes.txt").read_text(encoding="utf-8") == "user work"


async def test_a_holder_that_outlives_the_window_is_a_named_409_not_a_hang(
    container, lifecycle, session_id, monkeypatch
):
    """The window is bounded, and a permanent holder leaves everything intact.

    This is the guarantee step 6b of the acceptance run leans on: an editor (or
    a process we do not own) holding the workspace must produce the named
    workspace_busy error -- the row, the files and .trash all untouched, so the
    user can close the offending program and retry.
    """
    import time

    monkeypatch.setattr(lifecycle_module, "_TRASH_MOVE_ATTEMPTS", 5)
    monkeypatch.setattr(lifecycle_module, "_TRASH_MOVE_DELAY", 0.01)
    workspace = container.settings.workspace_dir / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notes.txt").write_text("user work", encoding="utf-8")

    calls: list[int] = []

    def always_locked(self, target):
        calls.append(1)
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "rename", always_locked)

    started = time.monotonic()
    with pytest.raises(WorkspaceBusyError) as caught:
        await lifecycle.delete(session_id)
    elapsed = time.monotonic() - started

    assert len(calls) == 5, "the retry must stop at the bounded attempt count"
    assert elapsed < 1.0, "a permanent holder must not turn the delete into a hang"
    message = str(caught.value)
    assert session_id in message, "the error must name the session that is stuck"
    assert "another program" in message and "delete it again" in message, "the cause must be actionable"
    assert await container.store.get_session(session_id) is not None, "the row was removed anyway"
    assert not list((container.settings.workspace_dir / ".trash").glob(session_id + "-*")), (
        "a failed delete moved the workspace to .trash anyway"
    )
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "user work"
