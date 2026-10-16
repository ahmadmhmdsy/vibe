from __future__ import annotations

from fastapi import APIRouter, Request

from vibe.api.deps import App, Owner, require_session
from vibe.api.errors import ApiError, ErrorCode
from vibe.auth import LOOPBACK_OWNER_ID

router = APIRouter()


@router.get("/sessions/{sid}/approvals")
async def list_approvals(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    store = deps.approval_store
    return [a.to_dict() for a in store.list(sid)]


@router.post("/approvals/{aid}/approve")
async def approve(aid: str, deps: App):
    store = deps.approval_store
    if store.get(aid) is None:
        raise ApiError(ErrorCode.NOT_FOUND, "not found")
    store.resolve(aid, True)
    return {"ok": True}


@router.post("/approvals/{aid}/deny")
async def deny(aid: str, deps: App):
    store = deps.approval_store
    if store.get(aid) is None:
        raise ApiError(ErrorCode.NOT_FOUND, "not found")
    store.resolve(aid, False)
    return {"ok": True}
