# services/vibe/src/vibe/doctor.py
"""Preflight checks: name the missing prerequisite, not the stack trace.

A fresh clone is usually missing something -- Chromium for Playwright, pnpm on
PATH, a provider key, or simply a free port. Starting the app in that state used
to fail deep inside a dependency with a traceback that named none of it. The
doctor answers the same question as one line per prerequisite plus the exact
command that fixes it.

It deliberately imports nothing from the app's runtime -- no FastAPI, no
uvicorn, no LangGraph, not even vibe.logging_setup -- so it still works when the
app cannot start at all. The only project import is Settings, which is
dataclasses and pathlib.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from vibe import registry
from vibe.config import Settings, local_app_data

MIN_PYTHON = (3, 13)
MIN_NODE = (20,)
#: Vite's own default. vite.config.ts sets no port today; see frontend_port().
VITE_DEFAULT_PORT = 5173
_VITE_CONFIG = "apps/vibe/vite.config.ts"


@dataclass(frozen=True)
class Check:
    """One prerequisite. remedy is the exact command to run when ok is False."""

    name: str
    ok: bool
    detail: str
    remedy: str = ""


#: Failures that mean the app cannot do its job, as opposed to one feature being
#: degraded (no browser download, no provider key yet). Only these make the
#: doctor exit non-zero, so a launcher stops on a real blocker rather than on a
#: nicety.
HARD_CHECKS = frozenset({"python", "node", "pnpm", "workspace", "port-backend", "port-frontend"})


def _which(name: str) -> str | None:
    """shutil.which wrapper: the single seam tests use to fake a missing tool."""
    return shutil.which(name)


def _command_version(cmd: list[str]) -> tuple[int, ...] | None:
    """The first dotted number a command prints, or None if it cannot run."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", proc.stdout or proc.stderr)
    if not match:
        return None
    return tuple(int(part) for part in match.groups() if part is not None)


def _python_exe() -> str:
    return sys.executable or "python"


def chromium_dirs() -> list[Path]:
    """Playwright's downloaded browsers, oldest first.

    Chromium is a separate download (`playwright install chromium`), so a fresh
    clone has the Python package and no browser -- which the user meets as "the
    browser tools are broken" in an otherwise healthy install.
    """
    roots: list[Path] = []
    if os.name == "nt":
        local = local_app_data()
        if local:
            roots.append(local / "ms-playwright")
    else:
        roots.append(Path.home() / ".cache" / "ms-playwright")
    found: list[Path] = []
    for root in roots:
        if root.is_dir():
            found.extend(sorted(p for p in root.glob("chromium*") if p.is_dir()))
    return found


def _repo_root() -> Path:
    """The checkout root, found by its most distinctive file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / _VITE_CONFIG).exists():
            return parent
    return here.parents[4]


def frontend_port(repo_root: Path | None = None) -> int:
    """The Vite dev-server port.

    vite.config.ts sets none today so Vite's own default applies, but reading
    the file means adding `server.port` there cannot silently desync the doctor.
    """
    root = repo_root or _repo_root()
    try:
        text = (root / _VITE_CONFIG).read_text(encoding="utf-8")
    except OSError:
        return VITE_DEFAULT_PORT
    match = re.search(r"\bport\s*:\s*(\d{2,5})", text)
    return int(match.group(1)) if match else VITE_DEFAULT_PORT


def port_free(host: str, port: int) -> bool:
    """True when nothing is listening on host:port.

    SO_REUSEADDR is deliberately NOT set on Windows: there it lets a second
    socket bind a port another process is actively listening on, which would
    turn this check into a rubber stamp.

    The family follows the host, so VIBE_HOST=::1 is tested on AF_INET6
    instead of being reported as a busy port that nothing is using.
    """
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        if os.name != "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _check_python() -> Check:
    wanted = ".".join(str(part) for part in MIN_PYTHON)
    ok = sys.version_info >= MIN_PYTHON
    return Check(
        "python",
        ok,
        platform.python_version(),
        "" if ok else f"install Python {wanted}+ and recreate the venv: python -m venv services/vibe/.venv",
    )


def _check_node() -> Check:
    exe = _which("node")
    if not exe:
        return Check("node", False, "not found on PATH", "install Node 20+ from https://nodejs.org and reopen the terminal")
    version = _command_version([exe, "--version"])
    if version is None:
        return Check("node", False, f"{exe} did not report a version", f"reinstall Node 20+ from https://nodejs.org (asked: {exe} --version)")
    ok = version >= MIN_NODE
    return Check("node", ok, ".".join(str(part) for part in version), "" if ok else "upgrade to Node 20+ from https://nodejs.org")


def _offline_note() -> str:
    """The network cause, for a remedy that tells the user to download something.

    Only called once a check has already failed, so the all-green path never
    waits on the network -- the doctor tests monkeypatch every other seam, and a
    probe in the happy path would make them depend on the machine's network.
    """
    if registry.reachable_sync():
        return ""
    return " - note: the npm registry is unreachable right now, so connect once and retry"


def _check_pnpm() -> Check:
    exe = _which("pnpm")
    if not exe:
        return Check("pnpm", False, "not found on PATH",
                     "install pnpm: npm install -g pnpm" + _offline_note())
    version = _command_version([exe, "--version"])
    if version is None:
        return Check("pnpm", False, f"{exe} did not report a version",
                     f"reinstall pnpm: npm install -g pnpm (asked: {exe} --version)" + _offline_note())
    return Check("pnpm", True, ".".join(str(part) for part in version))


def _check_uv() -> Check:
    exe = _which("uv")
    if not exe:
        return Check(
            "uv",
            False,
            "not found on PATH",
            "optional - install it from https://docs.astral.sh/uv/ to recreate the backend environment"
            + _offline_note(),
        )
    return Check("uv", True, exe)


def _check_chromium() -> Check:
    dirs = chromium_dirs()
    if not dirs:
        return Check("chromium", False, "no Playwright browser download found", f"{_python_exe()} -m playwright install chromium")
    return Check("chromium", True, f"{len(dirs)} browser build(s), newest {dirs[-1].name}")


def _check_workspace(settings: Settings) -> Check:
    workspace = settings.workspace_dir
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        probe = workspace / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Check("workspace", False, f"{workspace} is not usable ({exc})", "pick a writable directory: set VIBE_WORKSPACE_DIR=<path>")
    return Check("workspace", True, str(workspace))


def _custom_providers(path: Path) -> tuple[int | None, str]:
    """(count, detail). count is None when the file exists but cannot be read."""
    if not path.exists():
        return 0, f"{path.name} not created yet (no custom providers)"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path.name} is unreadable ({exc})"
    if not isinstance(data, dict):
        return None, f"{path.name} is not a provider map"
    return len(data), f"{len(data)} custom provider(s) in {path.name}"


def _check_providers_file(settings: Settings) -> Check:
    path = settings.workspace_dir / "providers.json"
    count, detail = _custom_providers(path)
    if count is None:
        remedy = f"fix or delete {path} - the app quarantines it to {path.name}.corrupt-<timestamp> and starts without custom providers"
        return Check("providers-file", False, detail, remedy)
    return Check("providers-file", True, detail)


def _check_providers_configured(settings: Settings) -> Check:
    keys = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "opencode-go": settings.opencode_api_key,
    }
    configured = [name for name, key in keys.items() if key]
    count, _ = _custom_providers(settings.workspace_dir / "providers.json")
    custom = count or 0
    if configured or custom:
        return Check("providers-configured", True, ", ".join([*configured, *([f"{custom} custom"] if custom else [])]))
    return Check(
        "providers-configured",
        False,
        "no provider has a key",
        "set OPENAI_API_KEY (or ANTHROPIC_API_KEY), or add a provider in the app's Settings panel",
    )


def _check_port(name: str, host: str, port: int, remedy: str) -> Check:
    if port_free(host, port):
        return Check(name, True, f"{host}:{port} is free")
    return Check(name, False, f"{host}:{port} is already in use", remedy)


def run_checks(settings: Settings) -> list[Check]:
    """Every prerequisite, in the order a user meets them."""
    web_port = frontend_port(_repo_root())
    return [
        _check_python(),
        _check_node(),
        _check_pnpm(),
        _check_uv(),
        _check_chromium(),
        _check_workspace(settings),
        _check_providers_file(settings),
        _check_providers_configured(settings),
        _check_port(
            "port-backend",
            settings.host,
            settings.port,
            f"stop what is using {settings.host}:{settings.port}, or start on another: set VIBE_PORT=<port>",
        ),
        _check_port(
            "port-frontend",
            settings.host,
            web_port,
            f"stop what is using port {web_port}, or change server.port in {_VITE_CONFIG}",
        ),
    ]


def hard_failures(checks: Sequence[Check]) -> list[Check]:
    return [check for check in checks if not check.ok and check.name in HARD_CHECKS]


def warnings(checks: Sequence[Check]) -> list[Check]:
    return [check for check in checks if not check.ok and check.name not in HARD_CHECKS]


def exit_code(checks: Sequence[Check]) -> int:
    """Non-zero only for a blocking failure, so a launcher can stop early."""
    return 1 if hard_failures(checks) else 0


def render(checks: Sequence[Check]) -> str:
    """One PASS/FAIL line per prerequisite, remedy underneath each failure."""
    width = max((len(check.name) for check in checks), default=0)
    lines: list[str] = []
    for check in checks:
        verdict = "PASS" if check.ok else "FAIL"
        lines.append(f"{verdict}  {check.name.ljust(width)}  {check.detail}".rstrip())
        if not check.ok and check.remedy:
            lines.append(f"      {' ' * width}  -> {check.remedy}")
    failed = hard_failures(checks)
    warned = warnings(checks)
    lines.append("")
    if failed:
        lines.append(f"{len(failed)} blocking problem(s): " + ", ".join(check.name for check in failed))
    if warned:
        lines.append(f"{len(warned)} warning(s): " + ", ".join(check.name for check in warned))
    if failed:
        lines.append("cannot start until the blocking problems above are fixed")
    elif warned:
        lines.append("no blocking problems - the app can start, with the warnings above")
    else:
        lines.append("all checks passed - the app can run on this machine")
    return "\n".join(lines)
