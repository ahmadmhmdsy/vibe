# tests/test_lifecycle.py
"""Session teardown and dev-server lifecycle (audit H3, and the leaked-process
half of it).

Deleting a session used to remove one sqlite row and nothing else, so a deleted
session kept its files on disk and kept a `pnpm dev` process running.
"""

import asyncio
import time
from pathlib import Path

import pytest

from vibe import lifecycle as lifecycle_module
from vibe.approvals import ApprovalStore
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.events import EventLog
from vibe.executor.base import DevServerHandle
from vibe.lifecycle import SessionLifecycle, WorkspaceBusyError
from vibe.models import ModelRef
from vibe.runs import RunRegistry, SessionKey
from vibe.store import SessionStore


class RecordingExecutor:
    """Stands in for a subprocess executor and records what was stopped."""

    def __init__(self):
        self.stopped = 0
        self._dev_server = DevServerHandle(port=5173, url="http://127.0.0.1:5173/", process=None)

    @property
    def dev_server_url(self):
        return self._dev_server.url

    async def stop_dev_server(self):
        self.stopped += 1
        self._dev_server = None

    async def close(self):
        # close() stops the dev server and releases the browser, so a deleted
        # session must show the dev server as stopped exactly once.
        await self.stop_dev_server()


def _lifecycle(tmp_path, **overrides):
    store = overrides.get("store") or SessionStore(tmp_path / "sessions.db")
    event_log = overrides.get("event_log") or EventLog(tmp_path / "events.db")
    return (
        store,
        event_log,
        SessionLifecycle(
            store=store,
            event_log=event_log,
            executors=overrides.get("executors", {}),
            autorun_policies=overrides.get("autorun_policies", {}),
            approvals=overrides.get("approvals", ApprovalStore()),
            runs=overrides.get("runs", RunRegistry()),
            workspace_dir=tmp_path,
        ),
    )


@pytest.mark.asyncio
async def test_delete_takes_everything_the_session_owned_with_it(tmp_path):
    store, event_log, lc = _lifecycle(tmp_path)
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))

    workspace = tmp_path / sid
    workspace.mkdir()
    (workspace / "package.json").write_text('{"name":"t"}')

    await event_log.append(sid, "user/message", {"content": "hi"})

    executor = RecordingExecutor()
    # The registries are keyed by (owner, session), so the test's dicts must be
    # too: keyed by the bare id they would prove nothing about the real lookup.
    key = SessionKey(owner_id=LOOPBACK_OWNER_ID, session_id=sid)
    executors = {key: executor}
    policies = {key: object()}
    approvals = ApprovalStore()
    approvals.create(sid, ["left-pad"])
    runs = RunRegistry()
    runs.start(sid)

    # The lifecycle must be built with the very dicts the test inspects,
    # otherwise it pops from its own empty registries.
    lc = SessionLifecycle(
        store=store,
        event_log=event_log,
        executors=executors,
        autorun_policies=policies,
        approvals=approvals,
        runs=runs,
        workspace_dir=tmp_path,
    )
    await lc.delete(sid)

    assert await store.get_session(sid) is None
    assert not workspace.exists(), "the workspace must not be left behind"
    assert list((tmp_path / ".trash").iterdir()), "it must be recoverable, not destroyed"
    assert await event_log.get(sid) == []
    assert executor.stopped == 1, "the dev server subprocess must be stopped"
    assert key not in executors
    assert key not in policies
    assert approvals.list(sid) == []
    assert runs.is_running(sid) is False


@pytest.mark.asyncio
async def test_delete_is_idempotent(tmp_path):
    store, _, lc = _lifecycle(tmp_path)
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    (tmp_path / sid).mkdir()

    await lc.delete(sid)
    await lc.delete(sid)  # a double-click must not raise

    assert await store.get_session(sid) is None


@pytest.mark.asyncio
async def test_delete_aborts_if_the_workspace_cannot_be_moved(tmp_path, monkeypatch):
    """The row is deleted last, so a failed move leaves the session intact."""
    store, _, lc = _lifecycle(tmp_path)
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    (tmp_path / sid).mkdir()

    def boom(self, target):
        raise OSError("directory is locked")

    monkeypatch.setattr(Path, "rename", boom)
    # The retry helper wraps the OS error in a named condition so the API can
    # answer 409 workspace_busy instead of 500. The property is unchanged: the
    # row is still here, because the move failed.
    monkeypatch.setattr(lifecycle_module, "_TRASH_MOVE_DELAY", 0)
    with pytest.raises(WorkspaceBusyError):
        await lc.delete(sid)

    assert await store.get_session(sid) is not None


# --- dev-server lifecycle -----------------------------------------------------


def test_restart_stops_the_previous_dev_server(tmp_path):
    from vibe.executor.local import LocalSubprocessExecutor

    ex = LocalSubprocessExecutor(workspace=tmp_path)
    calls = []

    async def fake_spawn():
        calls.append("spawn")
        return DevServerHandle(port=1, url="http://127.0.0.1:1/", process=None)

    async def fake_stop():
        calls.append("stop")

    ex._spawn = fake_spawn
    ex.stop_dev_server = fake_stop

    asyncio.run(ex.start_dev_server())
    asyncio.run(ex.start_dev_server())

    assert calls == ["spawn", "stop", "spawn"]


def test_idle_detection_respects_the_timeout(tmp_path):
    from vibe.executor.local import LocalSubprocessExecutor

    ex = LocalSubprocessExecutor(workspace=tmp_path)
    assert ex.is_idle(30) is False, "nothing is running"

    ex._dev_server = DevServerHandle(port=1, url="http://127.0.0.1:1/", process=None)
    ex._last_used = time.monotonic()
    assert ex.is_idle(30) is False, "just used"

    ex._last_used = time.monotonic() - 31 * 60
    assert ex.is_idle(30) is True
    assert ex.is_idle(0) is False, "a non-positive timeout disables reaping"


def test_read_console_logs_without_a_dev_server_returns_none(tmp_path):
    """No dev server means no page to read, so the answer is None.

    None -- not an empty string -- is what says `nobody read this`, so the
    autorun check can tell that apart from `it was clean`. An empty string
    would claim a clean console that nobody checked (audit M6).
    """
    from vibe.executor.local import LocalSubprocessExecutor

    ex = LocalSubprocessExecutor(workspace=tmp_path)
    assert asyncio.run(ex.read_console_logs(None)) is None
    assert asyncio.run(ex.screenshot(None)) is None


def test_browser_driver_reports_unavailable_when_it_cannot_launch(monkeypatch):
    """A machine without a browser still runs; it just cannot see the app.

    The driver must say so with None rather than raising, so a missing browser
    binary is a degraded install and not a crashed session.
    """
    from vibe.executor.browser import BrowserDriver

    async def no_browser(self):
        return None

    monkeypatch.setattr(BrowserDriver, "_ensure", no_browser)
    d = BrowserDriver()
    assert asyncio.run(d.read_console_logs("http://127.0.0.1:1/")) is None
    assert asyncio.run(d.screenshot("http://127.0.0.1:1/")) is None


@pytest.mark.parametrize(
    "level,kept",
    [
        ("error", {"error": True, "warning": False, "info": False}),
        ("warning", {"error": True, "warning": True, "info": False}),
        ("all", {"error": True, "warning": True, "info": True}),
    ],
)
def test_console_level_filtering(level, kept):
    """A healthy app prints warnings all day; only "error" must burn a fix
    iteration by default.
    """
    from vibe.executor.browser import _keep

    for message_type, expected in kept.items():
        assert _keep(message_type, level) is expected
