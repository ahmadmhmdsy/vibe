from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from vibe.api.deps import App, Owner, require_session
from vibe.api.errors import ApiError, ErrorCode
from vibe.api.schemas import CreateSessionIn, UpdateSessionIn, WriteFileIn
from vibe.api.sse import format_sse
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.lifecycle import WorkspaceBusyError
from vibe.models import ModelRef
from vibe.workspace import relative_files


def _parse_after_seq(raw) -> int:
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        raise ApiError(ErrorCode.VALIDATION_FAILED, "after_seq must be a non-negative integer") from None


router = APIRouter()


@router.post("/sessions", status_code=201)
async def create_session(body: CreateSessionIn, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    sid = await deps.session_service.create(
        ModelRef(provider_id=body.model.provider_id, model_id=body.model.model_id), owner
    )
    return {"id": sid}


@router.get("/sessions")
async def list_sessions(deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    sessions = await deps.session_service.list(owner)
    return [
        {
            "id": s.id,
            "title": s.title,
            "model": {"provider_id": s.model_ref.provider_id, "model_id": s.model_ref.model_id},
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in sessions
    ]


@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    s = await require_session(deps, sid, owner)
    # Same shape as a list row, including the timestamps the frontend's Session
    # type already declares (BE-10/FE-15): a client should not need a second
    # type for one session.
    return {
        "id": s.id,
        "title": s.title,
        "model": {"provider_id": s.model_ref.provider_id, "model_id": s.model_ref.model_id},
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


@router.get("/sessions/{sid}/usage")
async def session_usage(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    # Container.usage has no default and build always constructs a UsageTracker,
    # so the old `if usage is None` branch could never run, its NOT_FOUND was a
    # message no client could ever receive, and no test covered it (BE-10).
    usage = deps.usage
    total = await usage.session_total(sid)
    by_model = await usage.session_by_model(sid)
    return {
        "session_id": sid,
        "total_input_tokens": total.input_tokens,
        "total_output_tokens": total.output_tokens,
        "total_cached_tokens": total.cached_tokens,
        "total_cache_write_tokens": total.cache_write_tokens,
        "total_tokens": total.total_tokens,
        "total_cost_usd": total.cost_usd,
        "steps": total.steps,
        "by_model": [asdict(m) for m in by_model],
    }


@router.patch("/sessions/{sid}")
async def update_session(
    sid: str, request: Request, body: UpdateSessionIn, deps: App, owner: Owner = LOOPBACK_OWNER_ID
):
    await require_session(deps, sid, owner)
    if body.title is not None:
        await deps.session_service.rename(sid, body.title, owner)
    if body.model is not None:
        await deps.session_service.set_model(
            sid, ModelRef(provider_id=body.model.provider_id, model_id=body.model.model_id), owner
        )
    return {"ok": True}


@router.delete("/sessions/{sid}", status_code=204)
async def delete_session(sid: str, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    # Deliberately idempotent: deleting an already-deleted session is a no-op,
    # not a 404, so a double-click cannot surface an error.
    #
    # The service owns this, not the store: a session also owns a workspace
    # directory, a dev-server subprocess, an executor, an autorun policy, its
    # event log and any pending approvals. Deleting only the row left all of
    # them behind (audit H3).
    try:
        await deps.session_service.delete(sid, owner)
    except WorkspaceBusyError as exc:
        # The files are still open somewhere. Say so instead of a bare 500: the
        # session is untouched and deleting again works once it is closed.
        raise ApiError(ErrorCode.WORKSPACE_BUSY, str(exc)) from exc


@router.get("/sessions/{sid}/files")
async def list_files(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    ws = deps.session_service.workspace_path(sid)
    if not ws.exists():
        return []
    return relative_files(ws)


@router.get("/sessions/{sid}/files/{path:path}")
async def read_file(sid: str, request: Request, path: str, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    try:
        content = deps.session_service.read_text(sid, path)
    except FileNotFoundError:
        raise ApiError(ErrorCode.NOT_FOUND, "not found") from None
    return {"path": path, "content": content}


@router.put("/sessions/{sid}/files/{path:path}")
async def write_file(
    sid: str, request: Request, path: str, body: WriteFileIn, deps: App, owner: Owner = LOOPBACK_OWNER_ID
):
    await require_session(deps, sid, owner)
    try:
        deps.session_service.write_text(sid, path, body.content)
    except ValueError:
        raise ApiError(ErrorCode.VALIDATION_FAILED, "path outside workspace") from None
    return {"ok": True}


@router.get("/sessions/{sid}/events")
async def events(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    after_seq = _parse_after_seq(request.query_params.get("after_seq", 0))
    log = deps.event_log
    bus = deps.event_bus

    async def gen():
        # Subscribe before replaying: an event published between the replay
        # read and the subscription would otherwise be lost with nothing to
        # recover it. The overlap that creates is harmless because every event
        # carries a monotonic seq, so anything already replayed is skipped.
        subscription = bus.subscribe(sid)
        try:
            cursor = after_seq
            for e in await log.get(sid, after_seq):
                cursor = max(cursor, e.seq)
                yield format_sse(e)
            async for e in subscription:
                if e.seq <= cursor:
                    continue
                cursor = e.seq
                yield format_sse(e)
        except asyncio.CancelledError:
            return
        finally:
            await subscription.aclose()

    return StreamingResponse(gen(), media_type="text/event-stream")
