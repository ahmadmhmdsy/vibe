from fastapi import APIRouter

from vibe.api.deps import App
from vibe.providers.catalog import ProviderCatalog, ProviderInfo

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
        {**p.__dict__, "key_configured": key_status.get(p.id, False)}
        for p in ProviderCatalog().list_providers()
    ]
    # Merge user-defined custom providers (public fields only — never keys).
    customs = [
        ProviderInfo(
            id=p.id, name=p.name,
            capabilities={"tool_support": True, "vision": False},
            models=[{"id": m["id"], "name": m.get("name", m["id"])} for m in p.models],
            key_configured=bool(p.api_key),
        ).__dict__
        for p in deps.custom_provider_store.list()
    ]
    return builtins + customs
