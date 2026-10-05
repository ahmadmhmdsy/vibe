# services/vibe/src/vibe/providers/catalog.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderInfo:
    id: str
    name: str
    capabilities: dict  # {tool_support: bool, vision: bool}
    models: list  # [{id, name}]
    key_configured: bool = False  # masked status only — never the key itself

    def __contains__(self, key: object) -> bool:
        # Only the public field names are "in" a ProviderInfo — never secrets.
        return key in ("id", "name", "capabilities", "models", "key_configured")

class ProviderCatalog:
    """Returns only id, name, capabilities, models — never keys or base URLs."""
    def list_providers(self) -> list[ProviderInfo]:
        return [
            ProviderInfo("openai", "OpenAI", {"tool_support": True, "vision": True},
                         [{"id": "gpt-4o", "name": "GPT-4o"}, {"id": "gpt-4o-mini", "name": "GPT-4o mini"}]),
            ProviderInfo("anthropic", "Anthropic", {"tool_support": True, "vision": True},
                         [{"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"}]),
            ProviderInfo("opencode-go", "OpenCode Go", {"tool_support": True, "vision": False},
                         [{"id": "kimi-k3", "name": "Kimi K3"}, {"id": "grok-4.7", "name": "Grok 4.7"},
                          {"id": "deepseek-v4-flash", "name": "DeepSeek v4 Flash"}, {"id": "longcat-2.5-preview-free", "name": "LongCat 2.5 Preview Free"}]),
        ]
