# services/vibe/src/vibe/logging_setup.py
"""Process-wide logging configuration.

The backend had no logging at all before this module (audit H5): every
module was silent, so failures inside the idle-dev-server reaper and
inside a streaming chat run were swallowed by bare except blocks. A
preview that had crashed looked exactly like a preview that was idle.

The split follows the usual library/application convention:

* library modules only ever call logging.getLogger(__name__) and never
  configure handlers;
* the application entry point (python -m vibe) calls
  configure_logging() once, before serving.

When nobody calls configure_logging() -- tests, or a host application that
mounts the app itself -- the vibe logger keeps propagating to the root
logger, so the host's own logging setup still receives the records.

R5-T5 adds a rotating file handler under the workspace, so that "send me the
log" is answerable without hunting through a console nobody kept. The file
handler is opt-in at the call site (pass settings=... or log_file=...), which
keeps the old single-stderr-handler contract for a bare configure_logging() --
the audit tests pin that contract, and a host that mounts the app should not
have files appear behind its back. VIBE_LOG_FILE/VIBE_LOG_LEVEL are read by
config.py, so the environment reaches this module through Settings (L-6).
"""

from __future__ import annotations

import importlib.metadata
import logging
import logging.handlers
import platform
import shutil
import subprocess
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

#: Level used when neither the argument nor $VIBE_LOG_LEVEL is usable.
DEFAULT_LEVEL = "INFO"

#: Rotate at 2 MB and keep five files. Enough history for a bug report that
#: spans a few restarts, small enough that nobody has to think about disk
#: space. Overridable per call so a test can force rotation cheaply.
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"

#: A field whose name contains one of these is a credential. Matching on the
#: name rather than on a hand-kept list of exact fields means a github_token
#: added next year is redacted without anyone remembering to update this.
_SECRET_MARKERS = ("key", "token", "secret", "password", "credential")
_REDACTED = "***"

_VERSION_CACHE: dict[str, str] = {}


def _coerce_level(level: str | int) -> int:
    """Turn a level name or number into a logging level int.

    An unknown name falls back to DEFAULT_LEVEL rather than raising: a typo
    in VIBE_LOG_LEVEL should not stop the server from booting.
    """
    if isinstance(level, int):
        return level
    resolved = logging.getLevelName(level.strip().upper())
    # getLevelName returns "Level <NAME>" (a str) for anything it does not know.
    if isinstance(resolved, int):
        return resolved
    return logging.getLevelName(DEFAULT_LEVEL)


def _is_secret(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def redact_settings(settings: Any) -> dict[str, Any]:
    """A log-safe view of a settings object.

    dataclasses.asdict() would write openai_api_key=sk-... straight into the
    log file, so the value of every credential-shaped field is replaced
    instead. The decision is made by field name, not by a hand-maintained
    list, so a field added later is redacted by default. An unset secret stays
    None rather than becoming "***", so "configured but hidden" and "not
    configured" remain distinguishable in a bug report.
    """
    if is_dataclass(settings) and not isinstance(settings, type):
        items = [(f.name, getattr(settings, f.name, None)) for f in fields(settings)]
    else:
        try:
            items = list(vars(settings).items())
        except TypeError:
            return {"settings": repr(settings)}
    redacted: dict[str, Any] = {}
    for name, value in items:
        if _is_secret(name):
            redacted[name] = _REDACTED if value else None
        elif isinstance(value, Path):
            redacted[name] = str(value)
        else:
            redacted[name] = value
    return redacted


def _app_version() -> str:
    try:
        return importlib.metadata.version("vibe")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _tool_version(executable: str) -> str:
    """The first line of <tool> --version, or a word saying why not.

    Cached: the banner runs once per process, but tests configure logging
    several times, and spawning node twice for the same answer is waste. Every
    failure mode is a string, never an exception -- a machine without node must
    still start, and the sandbox may refuse the pipes this uses.
    """
    cached = _VERSION_CACHE.get(executable)
    if cached is not None:
        return cached
    version = "not found"
    found = shutil.which(executable)
    if found:
        try:
            completed = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=5, check=False)
            lines = (completed.stdout or completed.stderr).strip().splitlines()
            version = lines[0].strip() if lines else "unknown"
        except (OSError, subprocess.SubprocessError):
            version = "unknown"
    _VERSION_CACHE[executable] = version
    return version


def log_startup_banner(settings: Any, *, probe: bool = True) -> str:
    """Log one greppable line that a bug report can start with.

    A user reporting a problem should not have to recite their versions; the
    log file already contains them, together with the workspace path that
    identifies which install produced it. This never logs a credential: it
    reads only mode, port, workspace and log_file, and redact_settings is the
    only thing in this module that serialises a whole settings object.
    """
    logger = logging.getLogger("vibe.startup")
    message = "vibe startup: version=%s python=%s node=%s pnpm=%s mode=%s port=%s workspace=%s log_file=%s"
    args = (
        _app_version(),
        platform.python_version(),
        _tool_version("node") if probe else "unprobed",
        _tool_version("pnpm") if probe else "unprobed",
        getattr(settings, "mode", "unknown"),
        getattr(settings, "port", "unknown"),
        getattr(settings, "workspace_dir", "unknown"),
        getattr(settings, "log_file", None),
    )
    logger.info(message, *args)
    return message % args


def _file_handler(log_file: Path, max_bytes: int, backup_count: int) -> tuple[logging.Handler | None, str | None]:
    """A rotating handler, or (None, reason) if the path cannot be opened."""
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
    except OSError as exc:
        return None, f"{log_file}: {exc}"
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
    return handler, None


def _resolve_log_target(*, settings: Any | None, log_file: Path | str | None) -> Path | None:
    """Where the file handler writes, or None when nothing asked for a file."""
    if log_file is not None:
        return Path(log_file)
    if settings is not None:
        if not getattr(settings, "log_to_file", True):
            return None
        configured = getattr(settings, "log_file", None)
        return Path(configured) if configured is not None else None
    # No environment read here: VIBE_LOG_FILE is Settings.log_file's business
    # (guardrail L-6). A caller that wants a file passes settings= or log_file=.
    return None


def configure_logging(
    level: str | int | None = None,
    *,
    settings: Any | None = None,
    log_file: Path | str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> int:
    """Install the handlers this process logs through, and return the level.

    Idempotent: existing handlers are removed first, so calling this twice does
    not duplicate every line.

    Called with no arguments it installs exactly one stderr handler, which is
    the pre-R5-T5 contract. A rotating file handler is added -- and the startup
    banner logged -- when the call site says where the file goes: a settings
    object (settings.log_to_file / settings.log_file) or an explicit log_file=.
    VIBE_LOG_FILE and VIBE_LOG_LEVEL are read by config.py, so the supported way
    to set them from the environment is to pass settings=Settings.from_env()
    (that is what python -m vibe does).

    level defaults to the settings object's log_level, then to "INFO".

    A log file that cannot be opened is a warning on the console that is still
    working; it is never a reason the app fails to start.
    """
    if level is None:
        # VIBE_LOG_LEVEL reaches this through Settings.log_level, never through a
        # direct environment read (guardrail L-6).
        configured_level = getattr(settings, "log_level", None) if settings is not None else None
        level = configured_level or DEFAULT_LEVEL

    effective = _coerce_level(level)

    vibe_logger = logging.getLogger("vibe")
    vibe_logger.setLevel(effective)
    for existing in list(vibe_logger.handlers):
        vibe_logger.removeHandler(existing)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
    vibe_logger.addHandler(handler)
    # Our handler owns these records now; without this a host that also
    # configured the root logger would print every line twice.
    vibe_logger.propagate = False

    target = _resolve_log_target(settings=settings, log_file=log_file)
    if target is not None:
        file_handler, failure = _file_handler(Path(target), max_bytes, backup_count)
        if file_handler is None:
            vibe_logger.warning("cannot write the log file: %s", failure)
        else:
            vibe_logger.addHandler(file_handler)
            if settings is not None:
                try:
                    log_startup_banner(settings)
                except Exception:
                    # A banner is diagnostics; it must never be why a server
                    # fails to start.
                    vibe_logger.exception("could not write the startup banner")

    return effective
