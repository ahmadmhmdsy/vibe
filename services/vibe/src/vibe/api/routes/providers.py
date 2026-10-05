from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from vibe.api.deps import App
from vibe.api.errors import ApiError, ErrorCode
from vibe.providers.custom import CustomProvider

router = APIRouter()


def _public(p: CustomProvider) -> dict:
    return p.to_public()


@router.get("/providers")
async def list_providers(deps: App):
    store = deps.custom_provider_store
    return [_public(p) for p in store.list()]


# The wire format is camelCase (baseUrl/apiKey) because that is what the
# frontend sends; the dataclass is snake_case. Both spellings are accepted on
# every write so a field can never be dropped on the way in.
_FIELDS = {
    "name": "name",
    "baseUrl": "base_url",
    "base_url": "base_url",
    "apiKey": "api_key",
    "api_key": "api_key",
    "models": "models",
}


@router.post("/providers", status_code=201)
async def create_provider(request: Request, deps: App):
    body = await request.json()
    store = deps.custom_provider_store
    name = body.get("name")
    base_url = body.get("baseUrl") or body.get("base_url")
    if not name or not base_url:
        # A missing field used to surface as a KeyError -> 500.
        raise ApiError(ErrorCode.VALIDATION_FAILED, "name and baseUrl are required")
    p = CustomProvider(
        id=body.get("id") or uuid.uuid4().hex[:8],
        name=name,
        base_url=base_url,
        api_key=body.get("apiKey") or body.get("api_key") or "",
        models=body.get("models", []),
    )
    try:
        store.create(p)
    except ValueError as e:
        # from None: the ValueError text is the whole message; the chained
        # traceback would only add noise to a 409 the client can act on.
        raise ApiError(ErrorCode.CONFLICT, str(e)) from None
    return _public(p)


@router.patch("/providers/{pid}")
async def update_provider(pid: str, request: Request, deps: App):
    body = await request.json()
    store = deps.custom_provider_store
    # Filtering to snake_case alone silently dropped every camelCase field the
    # frontend sent, so base URL and API key edits never persisted.
    changes = {_FIELDS[k]: v for k, v in body.items() if k in _FIELDS}
    if not changes:
        raise ApiError(ErrorCode.VALIDATION_FAILED, f"no updatable fields in {sorted(body)}; expected one of {sorted(_FIELDS)}")
    try:
        p = store.update(pid, **changes)
    except KeyError:
        raise ApiError(ErrorCode.NOT_FOUND, "not found") from None
    return _public(p)


@router.delete("/providers/{pid}", status_code=204)
async def delete_provider(pid: str, deps: App):
    store = deps.custom_provider_store
    store.delete(pid)
