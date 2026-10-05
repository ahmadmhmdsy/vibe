# services/vibe/src/vibe/logging_setup.py
"""Process-wide logging configuration.

The backend had no logging at all before this module (audit H5): every
module was silent, so failures inside the idle-dev-server reaper and
inside a streaming chat run were swallowed by bare `except` blocks. A
preview that had crashed looked exactly like a preview that was idle.

The split follows the usual library/application convention:

* library modules only ever call `logging.getLogger(__name__)` and never
  configure handlers;
* the application entry point (`python -m vibe`) calls
  `configure_logging()` once, before serving.

When nobody calls `configure_logging()` — tests, or a host application
that mounts the app itself — the `vibe` logger keeps propagating to the
root logger, so the host's own logging setup still receives the records.
"""
from __future__ import annotations

import logging
import os
import sys

#: Level used when neither the argument nor $VIBE_LOG_LEVEL is usable.
DEFAULT_LEVEL = "INFO"

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


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


def configure_logging(level: str | int | None = None) -> int:
    """Install a stderr handler on the `vibe` logger tree.

    Idempotent: existing handlers are removed first, so calling this twice
    does not duplicate every line. Returns the effective level as an int.

    `level` defaults to $VIBE_LOG_LEVEL, then to "INFO".
    """
    if level is None:
        level = os.environ.get("VIBE_LOG_LEVEL") or DEFAULT_LEVEL

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

    return effective
