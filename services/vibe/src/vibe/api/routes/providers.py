from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Request

from vibe.api.deps import App
from vibe.api.errors import ApiError, ErrorCode
from vibe.api.schemas import SystemPromptIn
from vibe.prompts import DEFAULT_SYSTEM_PROMPT, system_prompt_for
from vibe.providers.custom import CustomProvider
from vibe.settings_store import resolve_prompt

router = APIRouter()


def _public(p: CustomProvider) -> dict:
    return p.to_public()


def _validate_models(raw: Any) -> list[dict[str, Any]]:
    """Validate and normalize the model list of a provider write.

    A model without an id used to be stored happily and only break later, when
    the catalog indexed m["id"] and answered 500 for every client (BE-13). The
    model's own keys are passed through untouched -- the UI owns e.g. protocol.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(ErrorCode.VALIDATION_FAILED, "models must be a list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, m in enumerate(raw):
        if not isinstance(m, dict):
            raise ApiError(ErrorCode.VALIDATION_FAILED, f"models[{i}] must be an object")
        mid = m.get("id")
        if not isinstance(mid, str) or not mid.strip():
            raise ApiError(ErrorCode.VALIDATION_FAILED, f"models[{i}].id is required")
        if mid in seen:
            raise ApiError(ErrorCode.VALIDATION_FAILED, f"duplicate model id '{mid}'")
        seen.add(mid)
        model = dict(m)
        if not isinstance(model.get("name"), str) or not model["name"]:
            model["name"] = mid
        out.append(model)
    return out


def _system_prompt_view(deps: App) -> dict:
    """The prompt the model will actually receive, and which layer chose it.

    Precedence is VIBE_SYSTEM_PROMPT > <workspace>/settings.json > the built-in
    default (BE-19). The environment is the documented operator override and
    keeps winning, which is why the GUI disables its field when source is "env":
    a user must not be able to type into a box that cannot take effect.
    """
    override, source = resolve_prompt(deps.settings, deps.settings_store)
    return {
        "configured": deps.settings.system_prompt or "",
        "effective": system_prompt_for(override),
        "default": DEFAULT_SYSTEM_PROMPT,
        "source": source,
    }


@router.get("/settings")
async def read_settings(deps: App):
    """The system prompt the agent will be given, and where it came from."""
    return {"system_prompt": _system_prompt_view(deps)}


@router.patch("/settings")
async def write_settings(deps: App, payload: SystemPromptIn):
    """Save (or clear) the workspace's system prompt.

    The write lands in <workspace>/settings.json, never in the environment: an
    app cannot rewrite its own operator configuration, and the next turn reads
    that file, so a save applies without a restart. An empty string clears the
    override and hands the field back to the built-in default.
    """
    # The store does blocking file I/O; keep it off the event loop.
    await asyncio.to_thread(deps.settings_store.write_system_prompt, payload.system_prompt)
    return {"system_prompt": _system_prompt_view(deps)}


@router.get("/providers")
async def list_providers(deps: App):
    store = deps.custom_provider_store
    # The store does blocking file I/O; keep it off the event loop.
    return [_public(p) for p in await asyncio.to_thread(store.list)]


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
    if not isinstance(body, dict):
        raise ApiError(ErrorCode.VALIDATION_FAILED, "the body must be a JSON object")
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
        models=_validate_models(body.get("models", [])),
    )
    try:
        await asyncio.to_thread(store.create, p)
    except ValueError as e:
        # from None: the ValueError text is the whole message; the chained
        # traceback would only add noise to a 409 the client can act on.
        raise ApiError(ErrorCode.CONFLICT, str(e)) from None
    return _public(p)


@router.patch("/providers/{pid}")
async def update_provider(pid: str, request: Request, deps: App):
    body = await request.json()
    if not isinstance(body, dict):
        raise ApiError(ErrorCode.VALIDATION_FAILED, "the body must be a JSON object")
    store = deps.custom_provider_store
    # Filtering to snake_case alone silently dropped every camelCase field the
    # frontend sent, so base URL and API key edits never persisted.
    changes = {_FIELDS[k]: v for k, v in body.items() if k in _FIELDS}
    if not changes:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED, f"no updatable fields in {sorted(body)}; expected one of {sorted(_FIELDS)}"
        )
    if "models" in changes:
        changes["models"] = _validate_models(changes["models"])
    try:
        p = await asyncio.to_thread(lambda: store.update(pid, **changes))
    except KeyError:
        raise ApiError(ErrorCode.NOT_FOUND, "not found") from None
    return _public(p)


@router.delete("/providers/{pid}", status_code=204)
async def delete_provider(pid: str, deps: App):
    store = deps.custom_provider_store
    await asyncio.to_thread(store.delete, pid)
