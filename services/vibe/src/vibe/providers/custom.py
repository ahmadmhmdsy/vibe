# services/vibe/src/vibe/providers/custom.py
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CustomProvider:
    """A user-defined provider row. The API key never leaves the server."""

    id: str
    name: str
    base_url: str
    api_key: str = ""
    models: list[dict[str, str]] = field(default_factory=list)  # [{id, name, protocol}]

    def to_public(self) -> dict[str, Any]:
        """Serialize for the frontend — never include the API key."""
        return {
            "id": self.id,
            "name": self.name,
            "baseUrl": self.base_url,
            "models": self.models,
            "key_configured": bool(self.api_key),
        }


class CustomProviderStore:
    """Persists custom providers to a JSON file inside the workspace dir.

    Keys are stored server-side only; the public serialization omits them.
    Every read-modify-write runs under one lock and every save is an atomic
    replace, so two concurrent requests cannot lose each other's provider and
    a crash mid-write cannot leave a truncated file (BE-15/BE-16).
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, CustomProvider]:
        """Read the store, degrading to empty rather than raising.

        A hand-edited or truncated file used to take down GET /providers and
        GET /catalog with a 500. A file we cannot parse is moved aside — so it
        can be inspected instead of silently overwritten — and the store
        continues empty.
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
        providers: dict[str, CustomProvider] = {}
        for key, value in data.items():
            try:
                providers[key] = CustomProvider(**value)
            except (TypeError, AttributeError):
                # One malformed row must not hide every other provider.
                logger.warning("ignoring malformed provider entry %r in %s", key, self._path)
        return providers

    def _quarantine(self, error: Exception) -> None:
        target = self._path.with_name(f"{self._path.name}.corrupt-{datetime.now(UTC):%Y%m%d-%H%M%S}")
        logger.warning("provider store %s is unreadable (%s); moving it to %s", self._path, error, target)
        try:
            self._path.replace(target)
        except OSError:
            logger.warning("could not move the unreadable provider store %s aside", self._path, exc_info=True)

    def _save(self, providers: dict[str, CustomProvider]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and replace: a reader (or a crash) sees either
        # the old file or the new one, never half of one.
        tmp = self._path.with_name(f"{self._path.name}.tmp")
        tmp.write_text(
            json.dumps({k: v.__dict__ for k, v in providers.items()}, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    def list(self) -> list[CustomProvider]:
        return list(self._load().values())

    def get(self, provider_id: str) -> CustomProvider | None:
        return self._load().get(provider_id)

    def create(self, p: CustomProvider) -> CustomProvider:
        with self._lock:
            providers = self._load()
            if p.id in providers:
                raise ValueError(f"provider '{p.id}' already exists")
            providers[p.id] = p
            self._save(providers)
        return p

    def update(self, provider_id: str, **changes: Any) -> CustomProvider:
        with self._lock:
            providers = self._load()
            if provider_id not in providers:
                raise KeyError(provider_id)
            p = providers[provider_id]
            for k, v in changes.items():
                if hasattr(p, k):
                    setattr(p, k, v)
            self._save(providers)
        return p

    def delete(self, provider_id: str) -> None:
        with self._lock:
            providers = self._load()
            providers.pop(provider_id, None)
            self._save(providers)
