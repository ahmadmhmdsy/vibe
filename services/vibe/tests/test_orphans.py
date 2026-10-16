# tests/test_orphans.py
"""R5-T9: reap dev servers a previous run left behind, and only those.

A crash leaves a listening process and a bound port that the next run cannot
reuse. The pidfile is a hint, not a source of truth: the recorded process may be
gone (on Windows the pnpm shim exits and leaves node listening) and a pid can be
reused by an unrelated process. So every candidate must pass two checks -- the
port is still held, and the command line names the workspace that recorded it --
and anything that cannot be verified is left alone.

Nothing here kills a process the test did not start. The dangerous path is the
one that proves it: a real process whose command line does *not* mention the
recorded workspace must survive the sweep.
"""
import asyncio
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from vibe.executor import local as local_module
from vibe.maintenance import (
    DEV_SERVERS_NAME,
    DevServerEntry,
    dev_servers_path,
    forget_dev_server,
    read_dev_servers,
    reap_dev_servers,
    record_dev_server,
    render_reap,
)

WINDOWS = pytest.mark.skipif(os.name != "nt", reason="these probes are the Windows ones")


def _entry(root: Path, name: str = "session-1", *, pid: int = 4242, port: int = 5199) -> DevServerEntry:
    return DevServerEntry(workspace=str(root / name), pid=pid, port=port,
                          started_at="2026-10-11T19:00:00+00:00")


class Probes:
    """The four questions the reaper asks, answered by the test."""

    def __init__(self, *, alive: bool = True, line: str | None = "own", owner: int | None = None,
                 bound: bool = True):
        self._alive = alive
        self._line = line
        self._owner = owner
        self._bound = bound
        self.killed: list[int] = []
        self.asked: list[str] = []

    def alive(self, pid: int) -> bool:
        self.asked.append(f"alive({pid})")
        return self._alive

    def command_line(self, pid: int) -> str | None:
        self.asked.append(f"command_line({pid})")
        if self._line == "own":
            return f"node {self.workspace} --port 5199" if self.workspace else "node"
        return self._line

    def port_owner(self, port: int) -> int | None:
        self.asked.append(f"port_owner({port})")
        return self._owner

    def port_bound(self, port: int) -> bool:
        self.asked.append(f"port_bound({port})")
        return self._bound

    def kill(self, pid: int) -> None:
        self.killed.append(pid)


def _probes(root: Path, name: str = "session-1", **kwargs) -> Probes:
    probes = Probes(**kwargs)
    probes.workspace = str(root / name)
    return probes


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _listening(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


# --- the pidfile -------------------------------------------------------------


def test_the_pidfile_round_trips_and_is_removed(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    assert read_dev_servers(tmp_path) == {entry.workspace: entry}
    assert forget_dev_server(tmp_path, entry.workspace) is True
    assert read_dev_servers(tmp_path) == {}
    assert forget_dev_server(tmp_path, entry.workspace) is False


def test_the_pidfile_is_the_documented_shape(tmp_path):
    entry = _entry(tmp_path, pid=11, port=22)
    record_dev_server(tmp_path, entry)
    raw = json.loads(dev_servers_path(tmp_path).read_text(encoding="utf-8"))
    assert list(raw) == ["dev_servers"]
    assert raw["dev_servers"][entry.workspace] == {
        "workspace": entry.workspace, "pid": 11, "port": 22,
        "started_at": "2026-10-11T19:00:00+00:00",
    }


def test_recording_again_replaces_the_entry_for_the_same_workspace(tmp_path):
    record_dev_server(tmp_path, _entry(tmp_path, pid=1))
    record_dev_server(tmp_path, _entry(tmp_path, pid=2))
    entries = read_dev_servers(tmp_path)
    assert len(entries) == 1
    assert next(iter(entries.values())).pid == 2


def test_an_unreadable_pidfile_is_ignored_not_repaired(tmp_path):
    dev_servers_path(tmp_path).write_text("{not json", encoding="utf-8")
    assert read_dev_servers(tmp_path) == {}
    report = reap_dev_servers(tmp_path, **_no_real_probes())
    assert report.reaped == [] and report.dropped == []
    assert dev_servers_path(tmp_path).read_text(encoding="utf-8") == "{not json"


def test_a_hand_edited_entry_without_a_pid_is_dropped(tmp_path):
    dev_servers_path(tmp_path).write_text(
        json.dumps({"dev_servers": {"/ws": {"port": 1}, "/ok": {"pid": 5, "port": 6}}}),
        encoding="utf-8",
    )
    entries = read_dev_servers(tmp_path)
    assert list(entries) == ["/ok"]
    assert entries["/ok"].pid == 5


def _no_real_probes(**overrides):
    """Probes that answer nothing real, for tests about the file alone."""
    probes = _probes(Path("."), **overrides)
    return {"alive": probes.alive, "command_line": probes.command_line,
            "port_owner": probes.port_owner, "port_bound": probes.port_bound, "kill": probes.kill}


# --- the sweep's decisions ---------------------------------------------------


def test_a_verified_orphan_is_killed_and_forgotten(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path)
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == [entry.pid]
    assert [e.pid for e in report.reaped] == [entry.pid]
    assert read_dev_servers(tmp_path) == {}


def test_an_unreadable_command_line_is_left_alone(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path, line=None)
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == [], "a process that cannot be identified is not killed"
    assert read_dev_servers(tmp_path) == {entry.workspace: entry}
    assert "could not be read" in report.skipped[0][1]


def test_a_foreign_process_on_the_recorded_port_survives(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path, line="C:/other/project/node.exe dev")
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == [], "the command line does not name this workspace"
    assert read_dev_servers(tmp_path) == {entry.workspace: entry}
    assert "foreign process" in report.skipped[0][1]


def test_a_dead_pid_with_the_port_still_held_kills_the_owner(tmp_path):
    """The Windows case: the pnpm shim exits and leaves node listening."""
    entry = _entry(tmp_path, pid=999999)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path, alive=False, owner=777)
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == [777]
    assert [e.pid for e in report.reaped] == [999999]
    assert read_dev_servers(tmp_path) == {}


def test_a_dead_pid_and_a_free_port_is_just_forgotten(tmp_path):
    entry = _entry(tmp_path, pid=999999)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path, alive=False, owner=None)
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == []
    assert [e.pid for e in report.dropped] == [999999]
    assert read_dev_servers(tmp_path) == {}


def test_an_alive_pid_that_is_not_listening_is_left_alone(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path, bound=False)
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == []
    assert read_dev_servers(tmp_path) == {entry.workspace: entry}
    assert "not held" in report.skipped[0][1]


def test_one_orphan_is_reaped_while_another_is_kept(tmp_path):
    reap = _entry(tmp_path, "session-1", pid=101)
    keep = _entry(tmp_path, "session-2", pid=202)
    record_dev_server(tmp_path, reap)
    record_dev_server(tmp_path, keep)
    probes = _probes(tmp_path)
    probes.command_line = lambda pid: str(tmp_path / "session-1") if pid == 101 else "C:/other/node"
    report = reap_dev_servers(tmp_path, alive=probes.alive, command_line=probes.command_line,
                              port_owner=probes.port_owner, port_bound=probes.port_bound,
                              kill=probes.kill)
    assert probes.killed == [101]
    assert [e.pid for e in report.reaped] == [101]
    assert read_dev_servers(tmp_path) == {keep.workspace: keep}


def test_the_report_renders_every_outcome(tmp_path):
    entry = _entry(tmp_path)
    record_dev_server(tmp_path, entry)
    probes = _probes(tmp_path)
    text = render_reap(reap_dev_servers(
        tmp_path, alive=probes.alive, command_line=probes.command_line,
        port_owner=probes.port_owner, port_bound=probes.port_bound, kill=probes.kill))
    assert "reaped orphan dev server" in text
    assert str(entry.pid) in text


# --- the executor records and forgets ----------------------------------------


@pytest.mark.asyncio
async def test_a_started_dev_server_is_recorded_and_a_stopped_one_is_forgotten(tmp_path, monkeypatch):
    """The wiring, without launching pnpm: spawn is stubbed at the process call."""
    from vibe.executor.local import LocalSubprocessExecutor

    class FakeStdout:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class FakeProc:
        pid = 4242
        returncode = None
        stdout = FakeStdout()

        def terminate(self):
            self.returncode = 0

        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(local_module.asyncio, "create_subprocess_exec", fake_exec)
    workspace = tmp_path / "ws" / "session-1"
    workspace.mkdir(parents=True)
    ex = LocalSubprocessExecutor(workspace=workspace, state_file=tmp_path / "ws" / DEV_SERVERS_NAME)

    handle = await ex.start_dev_server()
    entries = read_dev_servers(tmp_path / "ws")
    assert entries[str(workspace)] == DevServerEntry(
        workspace=str(workspace), pid=4242, port=handle.port,
        started_at=entries[str(workspace)].started_at,
    )
    assert entries[str(workspace)].started_at, "the start time is recorded for the reap log"

    await ex.stop_dev_server()
    assert read_dev_servers(tmp_path / "ws") == {}


def test_the_pidfile_defaults_to_the_workspace_root(tmp_path):
    """A session workspace is a directory under the workspace root."""
    from vibe.executor.local import LocalSubprocessExecutor

    workspace = tmp_path / "ws" / "session-1"
    workspace.mkdir(parents=True)
    ex = LocalSubprocessExecutor(workspace=workspace)
    assert ex._state_file == tmp_path / "ws" / DEV_SERVERS_NAME


# --- stopping a dev server must reap the process the shim wraps ---------------


#: What the wrapped process does: hold a file inside the workspace, exactly as a
#: vite dev server holds the session directory it serves.
_HOLD_THE_WORKSPACE = (
    "import sys, time\n"
    "f = open(sys.argv[1], 'ab')\n"
    "f.write(b'x')\n"
    "f.flush()\n"
    "time.sleep(120)\n"
)

#: The shape pnpm has: the direct child is a wrapper that spawns the real work
#: and waits for it. It reports the wrapped pid, so the test can watch it die.
_WRAP_AND_WAIT = (
    "import subprocess, sys\n"
    "p = subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])\n"
    "open(sys.argv[3], 'w').write(str(p.pid))\n"
    "p.wait()\n"
)


async def _wait_for_text(path: Path, timeout: float = 15.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
        await asyncio.sleep(0.05)
    raise AssertionError(str(path) + " was never written")


async def _wait_until_dead(pid: int, timeout: float = 15.0) -> bool:
    from vibe.maintenance import _process_alive

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return True
        await asyncio.sleep(0.05)
    return False


def _force_kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


@pytest.mark.asyncio
async def test_stopping_a_dev_server_reaps_the_process_the_shim_wraps(tmp_path):
    """The measured cause of DELETE -> 409 workspace_busy (acceptance step 6a).

    A real two-level chain, the shape pnpm has: a wrapper (the shim) whose child
    holds a file inside the session workspace, as vite does. The wrapped process
    survived a stop by 15+ minutes before the fix, because stop_dev_server()
    only terminated the wrapper -- so the workspace could never be moved aside.
    """
    from vibe.executor.base import DevServerHandle
    from vibe.executor.local import LocalSubprocessExecutor
    from vibe.maintenance import _process_alive

    workspace = tmp_path / "ws" / "session-1"
    workspace.mkdir(parents=True)
    held = workspace / "notes.txt"
    held.write_bytes(b"user work")
    pid_file = tmp_path / "wrapped.pid"

    wrapper = await asyncio.create_subprocess_exec(
        sys.executable, "-c", _WRAP_AND_WAIT, _HOLD_THE_WORKSPACE, str(held), str(pid_file),
        cwd=workspace, start_new_session=True,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    wrapped = int(await _wait_for_text(pid_file))
    try:
        assert _process_alive(wrapped), "the fixture must be running for this test to mean anything"
        ex = LocalSubprocessExecutor(workspace=workspace, state_file=tmp_path / "ws" / DEV_SERVERS_NAME)
        ex._dev_server = DevServerHandle(port=0, url="http://127.0.0.1:0/", process=wrapper)

        await ex.stop_dev_server()

        assert wrapper.returncode is not None, "the wrapper was not reaped"
        assert await _wait_until_dead(wrapped), (
            "the wrapped process survived the stop; it still holds the workspace, so "
            "DELETE /sessions/{id} can never move the workspace aside"
        )
        assert read_dev_servers(tmp_path / "ws") == {}, "a stopped server left its pidfile entry behind"
    finally:
        if _process_alive(wrapped):
            _force_kill(wrapped)
        if wrapper.returncode is None:
            wrapper.kill()
            await wrapper.wait()


# --- the real probes ---------------------------------------------------------


@WINDOWS
def test_the_real_probes_recognise_this_process_and_its_listener():
    from vibe.maintenance import _command_line, _port_bound, _port_owner, _process_alive

    assert _process_alive(os.getpid()) is True
    assert _process_alive(0) is False
    assert _process_alive(-1) is False
    assert "python" in (_command_line(os.getpid()) or "").lower()

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        assert _port_bound(port) is True
        assert _port_owner(port) == os.getpid()
    finally:
        listener.close()
    assert _port_bound(port) is False


def _spawn_holder(workspace: Path, port: int) -> subprocess.Popen:
    """A real process that holds a port and names the workspace on its command line."""
    code = (
        "import http.server, socketserver, sys\n"
        "socketserver.TCPServer.allow_reuse_address = True\n"
        "socketserver.TCPServer(('127.0.0.1', int(sys.argv[1])),"
        " http.server.SimpleHTTPRequestHandler).serve_forever()\n"
    )
    return subprocess.Popen([sys.executable, "-c", code, str(port), str(workspace)])


@WINDOWS
def test_a_real_orphan_is_reaped_and_a_real_foreign_process_is_not(tmp_path):
    """The whole point, with the real tasklist/CIM/netstat probes.

    Two real holders are started by this test. The first names its workspace on
    the command line and must die; the second names a different one, is recorded
    under the first workspace's name, and must survive -- proof that the guard,
    not luck, is what protects a foreign process.
    """
    root = tmp_path / "ws"
    own_ws = root / "session-a"          # holder A names this one: reaped
    other_ws = root / "session-b"        # holder B names this one...
    claimed = root / "session-claimed"   # ...but it is recorded under this one: kept
    stale_ws = root / "session-c"        # holder C names this one, recorded with a dead pid: reaped
    for path in (own_ws, other_ws, claimed, stale_ws):
        path.mkdir(parents=True)

    port_own, port_other, port_stale = _free_port(), _free_port(), _free_port()
    own = _spawn_holder(own_ws, port_own)
    other = _spawn_holder(other_ws, port_other)
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    stale = _spawn_holder(stale_ws, port_stale)
    try:
        assert _listening(port_own), "the holder never listened"
        assert _listening(port_other), "the second holder never listened"
        assert _listening(port_stale), "the third holder never listened"
        stamp = "2026-10-11T19:00:00+00:00"
        record_dev_server(root, DevServerEntry(str(own_ws), own.pid, port_own, stamp))
        record_dev_server(root, DevServerEntry(str(claimed), other.pid, port_other, stamp))
        # The recorded pid is gone; the port is held by a process started this
        # session whose command line names a workspace that was also recorded.
        record_dev_server(root, DevServerEntry(str(stale_ws), dead.pid, port_stale, stamp))

        report = reap_dev_servers(root)

        assert sorted(e.pid for e in report.reaped) == sorted([own.pid, dead.pid])
        assert own.poll() is not None, "the verified orphan must be gone"
        assert other.poll() is None, "a process that does not name the recorded workspace must survive"
        assert stale.poll() is not None, "the port owner is killed when the recorded pid is gone"
        assert read_dev_servers(root) == {
            str(claimed): DevServerEntry(str(claimed), other.pid, port_other, stamp)
        }, "only the unverifiable entry survives"
        assert not _listening(port_own, timeout=5)
    finally:
        for proc in (own, other, stale):
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)
