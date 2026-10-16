
# services/vibe/src/vibe/settings_store.py
"""Workspace-scoped settings the GUI may write (BE-19).

The system prompt has three possible homes, and the order between them is the
whole point of this module:

    VIBE_SYSTEM_PROMPT (environment)  >  <workspace>/settings.json  >  DEFAULT

The environment is the documented operator override and must keep winning, which
is why the Settings panel disables its field when the environment set one. The
file exists for the case the environment cannot serve: a prompt the user types in
the GUI. It is workspace-scoped because two sessions share one workspace, and it
is the seam that later becomes per-user state without moving any code.

Every write is a locked atomic replace and an unreadable file is moved aside
rather than raising, mirroring the custom-provider store (BE-15/BE-16). A missing
file, a corrupt file and a blank value all mean "no override", so the built-in
default is what the model receives - never an empty instruction set.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: The one key this store owns today. Unknown keys are preserved on write so a
#: later version and this one can share the file.
SYSTEM_PROMPT_KEY = "system_prompt"


class SettingsStore:
    """Reads and writes `<workspace_dir>/settings.json`."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> dict[str, Any]:
        """The stored object, degrading to {} rather than raising.

        A hand-edited or truncated file used to be an app-wide failure; here it is
        quarantined so it can be inspected instead of silently overwritten.
        """
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self._quarantine(e)
            return {}
        if not isinstance(data, dict):
            self._quarantine(ValueError(f"expected an object, found {type(data).__name__}"))
            return {}
        return data

    def _quarantine(self, error: Exception) -> None:
        target = self._path.with_name(f"{self._path.name}.corrupt-{datetime.now(UTC):%Y%m%d-%H%M%S}")
        logger.warning("settings file %s is unreadable (%s); moving it to %s", self._path, error, target)
        try:
            self._path.replace(target)
        except OSError:
            logger.warning("could not move the unreadable settings file %s aside", self._path, exc_info=True)

    def _save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and replace: a reader (or a crash) sees either
        # the old file or the new one, never half of one.
        tmp = self._path.with_name(f"{self._path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def read_system_prompt(self) -> str:
        """The saved prompt, or "" when none is saved (or none is readable)."""
        value = self._load().get(SYSTEM_PROMPT_KEY)
        return value.strip() if isinstance(value, str) else ""

    def write_system_prompt(self, prompt: str) -> str:
        """Persist (or clear) the prompt; returns the stored value.

        A blank prompt means "no override", so the key is removed rather than
        stored as "": a user who clears the field gets the built-in default back
        instead of a blank instruction set. The file itself is kept (with any
        other keys) because deleting a file is not how "unset one setting" should
        behave.
        """
        text = (prompt or "").strip()
        with self._lock:
            data = self._load()
            if text:
                data[SYSTEM_PROMPT_KEY] = text
            else:
                data.pop(SYSTEM_PROMPT_KEY, None)
            self._save(data)
        return text


def resolve_prompt(settings: Any, store: SettingsStore) -> tuple[str, str]:
    """The override in force and where it came from.

    Returns `(override, source)` where source is "env", "file" or "default". An
    empty override means "no override": the caller passes it to
    `vibe.prompts.system_prompt_for`, which substitutes the built-in default. The
    source name is exactly what the Settings panel prints, so the user can always
    tell which layer is winning.
    """
    env = (getattr(settings, "system_prompt", "") or "").strip()
    if env:
        return env, "env"
    saved = store.read_system_prompt()
    if saved:
        return saved, "file"
    return "", "default"


def effective_override(settings: Any, store: SettingsStore) -> str:
    """Just the override, for a caller that does not need the source."""
    return resolve_prompt(settings, store)[0]
