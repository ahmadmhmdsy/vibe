# services/vibe/src/vibe/providers/registry.py
"""The provider seam: provider id -> a configured LangChain chat model.

This is the *executed* abstraction. `LangGraphRuntime` calls the factory with a
`ModelRef` and drives a LangGraph tool loop, so what it actually needs is a chat
model exposing `bind_tools()`/`astream()` -- not a bespoke streaming protocol.

That logic used to live in `api/app.py`, which meant provider ids, base URLs and
headers were hard-coded in the web layer and adding a provider meant editing the
API module (audit H4). The three classes under `providers/` that claimed to be
the provider layer were never instantiated by production code -- and were broken
besides, constructing `ChatOpenAI(...)` with no `model=`. They were deleted
rather than wired: a seam whose tested half is unused and whose used half is
untested is worse than a single implementation.

Adding a provider is now two lines: write a `_build_<id>` function and add it to
`BUILTINS`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from vibe.models import ModelRef

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from vibe.config import Settings
    from vibe.providers.custom import CustomProviderStore


class LlmFactory(Protocol):
    """Builds a chat model for a model reference -- the runtime's only ask."""

    def __call__(self, model_ref: ModelRef, session_id: str | None = None) -> BaseChatModel: ...


class ProviderNotConfigured(ValueError):
    """The selected provider cannot be built: no key, or an unknown id.

    Subclasses ValueError so every existing `except ValueError` keeps working.
    It exists so the API layer can tell this apart from a generic bad value and
    answer with a code the UI can act on -- this is the one failure a user can
    be told how to fix.
    """


def _require(key: str | None, env_var: str) -> str:
    """Return the key, or fail with the message the UI already surfaces."""
    if not key:
        raise ProviderNotConfigured(f"{env_var} is not configured. Set it in .env or use a different provider.")
    return key


def _build_openai(settings: Settings, model_ref: ModelRef, session_id: str | None) -> BaseChatModel:
    api_key = _require(settings.openai_api_key, "OPENAI_API_KEY")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(api_key=api_key, model=model_ref.model_id, streaming=True)


def _build_anthropic(settings: Settings, model_ref: ModelRef, session_id: str | None) -> BaseChatModel:
    api_key = _require(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(api_key=api_key, model=model_ref.model_id, streaming=True)


def _build_opencode_go(settings: Settings, model_ref: ModelRef, session_id: str | None) -> BaseChatModel:
    api_key = _require(settings.opencode_api_key, "OPENCODE_API_KEY")
    from langchain_openai import ChatOpenAI

    # OpenCode Go routes by session, so it needs a stable x-opencode-session
    # header for shard affinity. Without a session id we send none rather than
    # an empty one.
    headers = {"x-opencode-session": session_id} if session_id else {}
    return ChatOpenAI(
        api_key=api_key,
        base_url="https://opencode.ai/zen/go/v1",
        model=model_ref.model_id,
        streaming=True,
        default_headers=headers,
    )


#: Built-in provider id -> builder. Adding a provider means adding a row here.
BUILTINS: dict[str, Callable[[Settings, ModelRef, str | None], BaseChatModel]] = {
    "openai": _build_openai,
    "anthropic": _build_anthropic,
    "opencode-go": _build_opencode_go,
}


def _build_custom(custom_store: CustomProviderStore | None, model_ref: ModelRef) -> BaseChatModel:
    """A user-defined provider, routed by the per-model protocol field."""
    custom = custom_store.get(model_ref.provider_id) if custom_store else None
    if custom is None:
        raise ProviderNotConfigured(f"unsupported provider: {model_ref.provider_id}")
    if not custom.api_key:
        raise ProviderNotConfigured(f"Custom provider '{model_ref.provider_id}' has no API key configured.")

    protocol = next(
        (m.get("protocol", "openai-chat") for m in custom.models if m["id"] == model_ref.model_id),
        "openai-chat",
    )
    if protocol == "anthropic-messages":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(api_key=custom.api_key, base_url=custom.base_url, model=model_ref.model_id, streaming=True)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(api_key=custom.api_key, base_url=custom.base_url, model=model_ref.model_id, streaming=True)


def build_llm_factory(settings: Settings, custom_store: CustomProviderStore | None = None) -> LlmFactory:
    """Return the factory `LangGraphRuntime` drives.

    A built-in id wins; anything else is looked up as a user-defined custom
    provider. An unknown id raises from `_build_custom` rather than returning
    `None`, so a typo surfaces as an error instead of a broken run.
    """

    def factory(model_ref: ModelRef, session_id: str | None = None) -> BaseChatModel:
        builder = BUILTINS.get(model_ref.provider_id)
        if builder is not None:
            return builder(settings, model_ref, session_id)
        return _build_custom(custom_store, model_ref)

    return factory
