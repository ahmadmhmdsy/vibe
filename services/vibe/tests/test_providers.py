# tests/test_providers.py
"""The provider seam (audit H4).

This file used to test a local stub against ChatRequest/ChatEvent -- types that
only the (dead, and broken) provider classes ever used, so it proved nothing
about production code. It now tests the registry that is actually executed.
"""

from pathlib import Path

import pytest

from vibe.config import Settings
from vibe.models import ModelRef
from vibe.providers.catalog import ProviderCatalog
from vibe.providers.custom import CustomProvider, CustomProviderStore
from vibe.providers.registry import BUILTINS, build_llm_factory


def _settings(tmp_path: Path, **keys) -> Settings:
    return Settings(workspace_dir=tmp_path / "ws", port=8000, **keys)


def _base_url(model) -> str:
    """ChatOpenAI and ChatAnthropic spell the base URL differently."""
    for attr in ("openai_api_base", "base_url", "anthropic_api_url"):
        value = getattr(model, attr, None)
        if value:
            return str(value)
    return ""


def test_builtins_cover_the_catalog():
    """Every provider the UI advertises must have a builder."""
    catalog_ids = {p.id for p in ProviderCatalog().list_providers()}
    assert catalog_ids <= set(BUILTINS)


def test_missing_key_names_the_env_var(tmp_path):
    factory = build_llm_factory(_settings(tmp_path))
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not configured"):
        factory(ModelRef("openai", "gpt-4o"))
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not configured"):
        factory(ModelRef("anthropic", "claude-sonnet-4-6"))
    with pytest.raises(ValueError, match="OPENCODE_API_KEY is not configured"):
        factory(ModelRef("opencode-go", "kimi-k3"))


def test_unknown_provider_is_an_error_not_a_none(tmp_path):
    """A typo must raise, not hand the runtime a broken model."""
    factory = build_llm_factory(_settings(tmp_path), custom_store=None)
    with pytest.raises(ValueError, match="unsupported provider: nope"):
        factory(ModelRef("nope", "m"))


def test_opencode_go_routes_by_session(tmp_path):
    factory = build_llm_factory(_settings(tmp_path, opencode_api_key="sk-test"))
    model = factory(ModelRef("opencode-go", "kimi-k3"), "sess-123")
    assert "opencode.ai" in _base_url(model)
    assert model.default_headers == {"x-opencode-session": "sess-123"}
    # No session id -> no header at all, rather than an empty one.
    assert factory(ModelRef("opencode-go", "kimi-k3")).default_headers == {}


def test_custom_provider_is_built_from_its_row(tmp_path):
    store = CustomProviderStore(tmp_path / "providers.json")
    store.create(
        CustomProvider(
            id="mine",
            name="Mine",
            base_url="http://localhost:1234/v1",
            api_key="sk-custom",
            models=[{"id": "m1", "name": "M1"}],
        )
    )
    model = build_llm_factory(_settings(tmp_path), store)(ModelRef("mine", "m1"))
    assert type(model).__name__ == "ChatOpenAI"
    assert _base_url(model) == "http://localhost:1234/v1"


def test_custom_provider_honours_the_per_model_protocol(tmp_path):
    store = CustomProviderStore(tmp_path / "providers.json")
    store.create(
        CustomProvider(
            id="mine",
            name="Mine",
            base_url="http://localhost:1234/v1",
            api_key="sk-custom",
            models=[{"id": "m1", "name": "M1", "protocol": "anthropic-messages"}],
        )
    )
    model = build_llm_factory(_settings(tmp_path), store)(ModelRef("mine", "m1"))
    assert type(model).__name__ == "ChatAnthropic"


def test_custom_provider_without_a_key_is_refused(tmp_path):
    store = CustomProviderStore(tmp_path / "providers.json")
    store.create(CustomProvider(id="mine", name="Mine", base_url="http://x/v1", api_key=""))
    factory = build_llm_factory(_settings(tmp_path), store)
    with pytest.raises(ValueError, match="has no API key configured"):
        factory(ModelRef("mine", "m1"))


def test_catalog_exposes_no_keys():
    cat = ProviderCatalog()
    providers = cat.list_providers()
    assert len(providers) > 0
    for p in providers:
        assert "apiKey" not in p
        assert "baseUrl" not in p
        assert "id" in p and "name" in p
