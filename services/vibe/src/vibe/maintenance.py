"""Back up and repair the local store (R5-T7 / AC-8).

Everything this app knows lives in files under the workspace: sessions and their
event history in two WAL SQLite databases, custom providers in
``providers.json``, and every generated project in its own directory. There is no
server to ask for help, so the user needs one command that saves that state and
one that can put it back.

Two rules shape this module:

* A backup is taken while the app may be running, so each database goes through
  ``sqlite3.Connection.backup``, which copies pages under a read transaction and
  produces one consistent, rolled-up file. ``shutil.copy2`` of a live WAL database
  can capture a torn file next to a stale ``-wal`` sidecar instead.
* Repair never deletes user data. A database that fails ``integrity_check`` is
  reported and left exactly where it is, and an unreadable ``providers.json`` is
  moved aside by the same code the app already uses on load -- not overwritten and
  not re-implemented here, so the two cannot drift apart.

Generated projects are deliberately not copied: a backup that moved or rewrote a
user's source tree would be worse than none. Only the two databases and the
provider file are saved.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DB_NAMES = ("sessions.db", "events.db")
PROVIDERS_NAME = "providers.json"
BACKUPS_DIRNAME = "backups"
MANIFEST_NAME = "manifest.json"
KEEP_DEFAULT = 7

# Only directories whose name is a timestamp we wrote are ours to prune. A
# stray folder under backups/ belongs to the user, and losing it would be
# exactly the failure this command exists to prevent.
_STAMP = re.compile(r"^\d{8}-\d{6}(-\d+)?$")


@dataclass
class BackupResult:
    directory: Path
    files: dict[str, int] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        return sum(self.files.values())

    @property
    def ok(self) -> bool:
        """False if something that exists could not be copied."""
        return not self.errors


@dataclass
class RepairReport:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append((name, ok, detail))

    @property
    def ok(self) -> bool:
        return not self.errors


def backup(
    workspace: Path | str,
    keep: int | None = None,
    *,
    timestamp: str | None = None,
) -> BackupResult:
    """Save the databases and the provider file into ``<workspace>/backups/<ts>/``.

    ``keep`` is how many backups remain afterwards (newest first). A file that
    is not there is skipped, not an error: a fresh install has nothing to save
    yet. A file that is there and cannot be copied is an error, and the partial
    result is still reported so the user can see which source to fix.
    """
    workspace = Path(workspace)
    keep = KEEP_DEFAULT if keep is None else keep
    if keep < 1:
        raise ValueError("keep must be at least 1; pruning everything would delete the backup just taken")

    root = workspace / BACKUPS_DIRNAME
    target = _new_backup_dir(root, timestamp)
    result = BackupResult(directory=target)

    for name in DB_NAMES:
        source = workspace / name
        if not source.exists():
            result.missing.append(name)
            continue
        try:
            _snapshot(source, target / name)
        except sqlite3.Error as error:
            result.errors.append(f"{name}: {error}")
        else:
            result.files[name] = (target / name).stat().st_size

    providers = workspace / PROVIDERS_NAME
    if not providers.exists():
        result.missing.append(PROVIDERS_NAME)
    else:
        try:
            shutil.copy2(providers, target / PROVIDERS_NAME)
        except OSError as error:
            result.errors.append(f"{PROVIDERS_NAME}: {error}")
        else:
            result.files[PROVIDERS_NAME] = (target / PROVIDERS_NAME).stat().st_size

    _write_manifest(target, result)
    result.removed = _prune(root, keep)
    return result


def repair(workspace: Path | str) -> RepairReport:
    """Check what can be checked, re-run migrations, and quarantine an unreadable providers file.

    Returns a report rather than raising: every problem found is one line the
    user can act on, and the exit code is non-zero only when something could not
    be fixed. Nothing on disk is deleted, ever.
    """
    workspace = Path(workspace)
    report = RepairReport()
    if not workspace.exists():
        report.errors.append(f"workspace {workspace} does not exist")
        return report
    for name in DB_NAMES:
        _repair_database(workspace / name, report)
    _repair_providers(workspace / PROVIDERS_NAME, report)
    return report


def render_backup(result: BackupResult) -> str:
    lines = [f"backup: {result.directory}"]
    for name, size in sorted(result.files.items()):
        lines.append(f"  saved   {name} ({size} bytes)")
    for name in result.missing:
        lines.append(f"  skipped {name} (not present)")
    for path in result.removed:
        lines.append(f"  pruned  {path.name}")
    for error in result.errors:
        lines.append(f"  FAILED  {error}")
    state = "ok" if result.ok else "INCOMPLETE"
    lines.append(f"backup {state}: {result.size_bytes} bytes in {len(result.files)} file(s)")
    if not result.ok:
        lines.append("the sources that failed are still in place; fix them and run `vibe backup` again")
    return "\n".join(lines)


def render_repair(report: RepairReport) -> str:
    lines = ["repair:"]
    for name, ok, detail in report.checks:
        lines.append(f"  {'ok      ' if ok else 'PROBLEM '} {name}: {detail}")
    for action in report.actions:
        lines.append(f"  action  {action}")
    for error in report.errors:
        lines.append(f"  FAILED  {error}")
    state = "ok" if report.ok else "incomplete"
    lines.append(f"repair {state}: {len(report.errors)} problem(s) left to fix")
    if not report.ok:
        lines.append("nothing was deleted; the unusable files are still in the workspace")
    return "\n".join(lines)


def backup_exit_code(result: BackupResult) -> int:
    """0 saved, 1 something that exists could not be saved (a .bat can test %errorlevel%)."""
    return 0 if result.ok else 1


def repair_exit_code(report: RepairReport) -> int:
    return 0 if report.ok else 1


def _snapshot(sqlite_path: Path, target: Path) -> None:
    """Copy one database through sqlite's own backup API.

    The API walks the source under a read transaction and writes a complete
    database to the destination, so a writer in another process cannot make the
    copy torn. Opening read-write (not ``mode=ro``) is deliberate: sqlite needs
    to create the ``-shm``/``-wal`` sidecars for a WAL database, and a read-only
    connection to one without them fails outright.
    """
    source = sqlite3.connect(str(sqlite_path), timeout=5.0)
    try:
        destination = sqlite3.connect(str(target), timeout=5.0)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def _new_backup_dir(root: Path, timestamp: str | None) -> Path:
    stamp = timestamp or dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    candidate = root / stamp
    suffix = 2
    while candidate.exists():
        candidate = root / f"{stamp}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _write_manifest(target: Path, result: BackupResult) -> None:
    manifest = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "files": result.files,
        "missing": result.missing,
        "size_bytes": result.size_bytes,
        "sqlite_version": sqlite3.sqlite_version,
    }
    (target / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _prune(root: Path, keep: int) -> list[Path]:
    """Drop our oldest backups, newest ``keep`` survive. Never touches anything else."""
    ours = sorted(
        (path for path in root.iterdir() if path.is_dir() and _STAMP.match(path.name)),
        key=lambda path: path.name,
    )
    removed: list[Path] = []
    for stale in ours[:-keep]:
        shutil.rmtree(stale, ignore_errors=True)
        removed.append(stale)
    return removed


def _integrity(path: Path) -> tuple[bool, str]:
    """``PRAGMA integrity_check`` on one database, as (ok, human detail)."""
    try:
        connection = sqlite3.connect(str(path), timeout=5.0)
    except sqlite3.Error as error:
        return False, str(error)
    try:
        rows = [str(row[0]) for row in connection.execute("PRAGMA integrity_check").fetchall()]
    except sqlite3.Error as error:
        return False, str(error)
    finally:
        connection.close()
    return rows == ["ok"], "; ".join(rows) or "no result"


def _repair_database(path: Path, report: RepairReport) -> None:
    if not path.exists():
        report.add(path.name, True, "not present (nothing to check)")
        return
    healthy, detail = _integrity(path)
    report.add(path.name, healthy, detail)
    if not healthy:
        # Left in place on purpose: a user can still try to read it, and a
        # backup taken before the damage is the documented way back.
        report.errors.append(f"{path.name} failed integrity_check and was left untouched: {detail}")
        return
    try:
        if path.name == "sessions.db":
            from vibe.store import SessionStore

            SessionStore(path)
        else:
            from vibe.events import EventLog

            EventLog(path)
    except Exception as error:  # report, never crash a repair command
        report.errors.append(f"{path.name}: could not re-run migrations: {error}")
    else:
        report.actions.append(f"{path.name}: migrations are up to date")


def _readable_json(path: Path) -> bool:
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
    except (OSError, ValueError):
        return False


def _repair_providers(path: Path, report: RepairReport) -> None:
    if not path.exists():
        report.add(PROVIDERS_NAME, True, "not present (nothing to check)")
        return
    pattern = f"{path.name}.corrupt-*"
    before = {found.name for found in path.parent.glob(pattern)}
    # Reuse the app's own load path (R2-T4): CustomProviderStore moves a file it
    # cannot parse to providers.json.corrupt-<ts> and carries on empty. Repair
    # does not re-implement that move, so the two can never disagree.
    from vibe.providers.custom import CustomProviderStore

    providers = CustomProviderStore(path).list()
    quarantined = sorted({found.name for found in path.parent.glob(pattern)} - before)
    if quarantined:
        report.add(PROVIDERS_NAME, False, f"unreadable; moved aside as {quarantined[-1]}")


        report.actions.append(
            f"{PROVIDERS_NAME}: quarantined to {quarantined[-1]} (the original bytes are preserved)"
        )
    elif path.exists() and not _readable_json(path):
        report.add(PROVIDERS_NAME, False, f"unreadable and could not be moved aside; still at {path}")
        report.errors.append(f"{PROVIDERS_NAME}: unreadable and could not be quarantined (see the log)")
    else:
        report.add(PROVIDERS_NAME, True, f"readable ({len(providers)} provider(s))")
        report.actions.append(f"{PROVIDERS_NAME}: left unchanged")

# --- orphan dev servers (R5-T9) ----------------------------------------------

#: Where an executor records the dev servers it started. One file per workspace
#: root, keyed by session workspace, so a process that dies before stopping its
#: server still leaves the next run a list to act on.
DEV_SERVERS_NAME = "dev-servers.json"
DEV_SERVERS_KEY = "dev_servers"


@dataclass(frozen=True)
class DevServerEntry:
    """One dev server an executor started and has not stopped."""

    workspace: str
    pid: int
    port: int
    started_at: str = ""


@dataclass
class ReapReport:
    """What the orphan sweep did, so a caller can log it and a test can assert it."""

    reaped: list[DevServerEntry] = field(default_factory=list)
    kept: list[DevServerEntry] = field(default_factory=list)
    dropped: list[DevServerEntry] = field(default_factory=list)
    #: (entry, why) for everything left alone -- "why not" is never a guess.
    skipped: list[tuple[DevServerEntry, str]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.reaped or self.dropped)


# Reentrant: record/forget read-modify-write through write_dev_servers, and the
# sweep writes the survivors back while it still holds the lock.
_file_lock = threading.RLock()


def dev_servers_path(root: Path | str) -> Path:
    """The pidfile for a workspace root."""
    return Path(root) / DEV_SERVERS_NAME


def read_dev_servers(root: Path | str) -> dict[str, DevServerEntry]:
    """The recorded entries, or {} when the file is missing or unreadable.

    A pidfile is a hint that saves a process kill, never a source of truth, so a
    corrupt one is ignored rather than repaired -- and a hand-edited entry that
    does not parse is dropped instead of guessed at.
    """
    try:
        raw = json.loads(dev_servers_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = raw.get(DEV_SERVERS_KEY) if isinstance(raw, dict) else None
    if not isinstance(items, dict):
        return {}
    entries: dict[str, DevServerEntry] = {}
    for key, item in items.items():
        if not isinstance(item, dict):
            continue
        try:
            entries[str(key)] = DevServerEntry(
                workspace=str(item.get("workspace", key)),
                pid=int(item["pid"]),
                port=int(item["port"]),
                started_at=str(item.get("started_at", "")),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return entries


def write_dev_servers(root: Path | str, entries: dict[str, DevServerEntry]) -> None:
    """Replace the pidfile atomically, so a reader never sees it half-written."""
    path = dev_servers_path(root)
    payload = {
        DEV_SERVERS_KEY: {
            key: {
                "workspace": entry.workspace,
                "pid": entry.pid,
                "port": entry.port,
                "started_at": entry.started_at,
            }
            for key, entry in entries.items()
        }
    }
    with _file_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)


def record_dev_server(root: Path | str, entry: DevServerEntry) -> None:
    """Add or replace one server's entry. Called when it starts."""
    with _file_lock:
        entries = read_dev_servers(root)
        entries[entry.workspace] = entry
        write_dev_servers(root, entries)


def forget_dev_server(root: Path | str, workspace: str) -> bool:
    """Drop the entry for a workspace. Called when its server stops."""
    with _file_lock:
        entries = read_dev_servers(root)
        if workspace not in entries:
            return False
        del entries[workspace]
        write_dev_servers(root, entries)
        return True


def _port_bound(port: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    """True while something accepts connections on the port.

    A plain connect, so it needs no netstat or lsof and answers the same way on
    every platform. The connection is closed immediately.
    """
    if port <= 0:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _process_alive(pid: int) -> bool:
    """True while a process with this pid exists."""
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) is NOT a liveness test on Windows -- it terminates the
        # process -- so ask tasklist, which is read-only.
        proc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return f'"{pid}"' in proc.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists; it belongs to someone else
    return True


def _command_line(pid: int) -> str | None:
    """The full command line of a process, or None when it cannot be read.

    None has meaning: nothing could be verified about this pid, and the reaper
    treats that as "do not kill". A process whose owner cannot be identified is
    a foreign process until proven otherwise (repository rule).
    """
    if os.name == "nt":
        script = f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine"
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=60, check=False,
        )
        line = proc.stdout.strip()
        return line or None
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    return raw.replace(b"\x00", b" ").decode(errors="replace").strip() or None


def _port_owner(port: int) -> int | None:
    """The pid listening on a port, or None when it cannot be determined."""
    if port <= 0:
        return None
    if os.name == "nt":
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        for line in proc.stdout.splitlines():
            parts = line.split()
            listening = (
                len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING"
            )
            if listening and parts[1].endswith(f":{port}"):
                try:
                    return int(parts[4])
                except ValueError:
                    return None
        return None
    lsof = shutil.which("lsof")
    if lsof is None:
        return None
    proc = subprocess.run(
        [lsof, "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    found = proc.stdout.split()
    try:
        return int(found[0])
    except (IndexError, ValueError):
        return None


def _kill_process(pid: int) -> None:
    """Kill a verified dev server, and its children on Windows."""
    if pid <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, timeout=60, check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(10):
        time.sleep(0.1)
        if not _process_alive(pid):
            return
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


def reap_dev_servers(
    root: Path | str,
    *,
    alive: Callable[[int], bool] = _process_alive,
    command_line: Callable[[int], str | None] = _command_line,
    port_owner: Callable[[int], int | None] = _port_owner,
    port_bound: Callable[[int], bool] = _port_bound,
    kill: Callable[[int], None] = _kill_process,
    timestamp: str | None = None,
) -> ReapReport:
    """Kill dev servers this app left behind, and never a foreign process.

    A crash leaves a listening process and a bound port the next run cannot
    reuse. The recorded pid is only a hint: it may already be gone (on Windows
    the pnpm shim exits and leaves node listening) and a pid can be reused by an
    unrelated process. Every candidate must therefore pass two checks -- the port
    is still held, and the command line names the workspace that recorded it --
    and anything that cannot be verified is left alone and reported.
    """
    report = ReapReport()
    entries = read_dev_servers(root)
    if not entries:
        return report
    survivors: dict[str, DevServerEntry] = {}
    for workspace, entry in entries.items():
        still_alive = alive(entry.pid)
        owner = port_owner(entry.port) if not still_alive else None
        target = entry.pid if still_alive else owner
        if target is None:
            report.dropped.append(entry)
            continue
        if not port_bound(entry.port):
            # Alive but not serving: starting up, restarting, or an unrelated
            # process. Not ours to kill, so the entry is kept for the next run.
            survivors[workspace] = entry
            report.kept.append(entry)
            report.skipped.append((entry, f"pid {target} is alive but port {entry.port} is not held"))
            continue
        if target != entry.pid:
            logger.info(
                "dev server for %s: recorded pid %s is gone, port %s is held by pid %s",
                workspace, entry.pid, entry.port, target,
            )
        line = command_line(target)
        if not line:
            survivors[workspace] = entry
            report.kept.append(entry)
            report.skipped.append(
                (entry, f"the command line of pid {target} could not be read; not killing it")
            )
            continue
        if workspace not in line:
            survivors[workspace] = entry
            report.kept.append(entry)
            report.skipped.append(
                (entry, f"pid {target} does not mention {workspace}; not killing a foreign process")
            )
            continue
        kill(target)
        report.reaped.append(entry)
        logger.info(
            "reaped orphan dev server for %s (pid %s, port %s, started %s)",
            workspace, target, entry.port, entry.started_at or "unknown",
        )
    if report.changed:
        write_dev_servers(root, survivors)
    return report


def render_reap(report: ReapReport) -> str:
    """One line per outcome, for the startup log."""
    lines: list[str] = []
    for entry in report.reaped:
        lines.append(f"reaped orphan dev server for {entry.workspace} (pid {entry.pid}, port {entry.port})")
    for entry in report.dropped:
        lines.append(f"forgot dev server for {entry.workspace} (pid {entry.pid} is gone)")
    for entry, why in report.skipped:
        lines.append(f"left dev server for {entry.workspace} alone: {why}")
    return "\n".join(lines)
