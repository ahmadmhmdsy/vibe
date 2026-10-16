from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from vibe.api.deps import App
from vibe.providers.catalog import ProviderCatalog, ProviderInfo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/catalog")
async def catalog(deps: App):
    settings = deps.settings
    key_status = {
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "opencode-go": bool(settings.opencode_api_key),
    }
    builtins = [
        {**p.__dict__, "key_configured": key_status.get(p.id, False)} for p in ProviderCatalog().list_providers()
    ]
    # Merge user-defined custom providers (public fields only — never keys).
    # The store is read off the event loop: it is file I/O, and every other
    # route already hands it to a thread.
    customs = []
    for p in await asyncio.to_thread(deps.custom_provider_store.list):
        models = []
        for m in p.models:
            # A model without an id used to raise KeyError right here, which
            # turned one bad store entry into a 500 for every client (BE-13).
            mid = m.get("id") if isinstance(m, dict) else None
            if not isinstance(mid, str) or not mid:
                logger.warning("provider %s has a model without an id; skipping it", p.id)
                continue
            models.append({"id": mid, "name": m.get("name") or mid})
        customs.append(
            ProviderInfo(
                id=p.id,
                name=p.name,
                capabilities={"tool_support": True, "vision": False},
                models=models,
                key_configured=bool(p.api_key),
            ).__dict__
        )
    return builtins + customs
