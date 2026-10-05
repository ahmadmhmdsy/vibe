# services/vibe/src/vibe/providers/custom.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    """

    def __init__(self, path: Path):
        self._path = path

    def _load(self) -> dict[str, CustomProvider]:
        if not self._path.exists():
            return {}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return {k: CustomProvider(**v) for k, v in data.items()}

    def _save(self, providers: dict[str, CustomProvider]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({k: v.__dict__ for k, v in providers.items()}, indent=2),
            encoding="utf-8",
        )

    def list(self) -> list[CustomProvider]:
        return list(self._load().values())

    def get(self, provider_id: str) -> CustomProvider | None:
        return self._load().get(provider_id)

    def create(self, p: CustomProvider) -> CustomProvider:
        providers = self._load()
        if p.id in providers:
            raise ValueError(f"provider '{p.id}' already exists")
        providers[p.id] = p
        self._save(providers)
        return p

    def update(self, provider_id: str, **changes: Any) -> CustomProvider:
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
        providers = self._load()
        providers.pop(provider_id, None)
        self._save(providers)
