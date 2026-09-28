from __future__ import annotations
import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from vibe.models import ModelRef
from vibe.api.sse import format_sse

router = APIRouter()

@router.post("/sessions", status_code=201)
async def create_session(body: dict, request: Request):
    mr = ModelRef(**body["model"])
    sid = await request.app.state.store.create_session(mr)
    return {"id": sid}

@router.get("/sessions")
async def list_sessions(request: Request):
    sessions = await request.app.state.store.list_sessions()
    return [{"id": s.id, "title": s.title, "model": {"provider_id": s.model_ref.provider_id, "model_id": s.model_ref.model_id},
             "created_at": s.created_at, "updated_at": s.updated_at} for s in sessions]

@router.get("/sessions/{sid}")
async def get_session(sid: str, request: Request):
    s = await request.app.state.store.get_session(sid)
    if not s: raise HTTPException(404, "not found")
    return {"id": s.id, "title": s.title, "model": {"provider_id": s.model_ref.provider_id, "model_id": s.model_ref.model_id}}

@router.patch("/sessions/{sid}")
async def rename_session(sid: str, body: dict, request: Request):
    await request.app.state.store.rename_session(sid, body["title"])
    return {"ok": True}

@router.delete("/sessions/{sid}", status_code=204)
async def delete_session(sid: str, request: Request):
    await request.app.state.store.delete_session(sid)

@router.get("/sessions/{sid}/events")
async def events(sid: str, request: Request):
    after_seq = int(request.query_params.get("after_seq", 0))
    log = request.app.state.event_log
    bus = request.app.state.event_bus
    async def gen():
        import asyncio
        # replay missed events
        for e in await log.get(sid, after_seq):
            yield format_sse(e)
        # live stream
        try:
            async for e in bus.subscribe(sid):
                yield format_sse(e)
        except asyncio.CancelledError:
            return
    return StreamingResponse(gen(), media_type="text/event-stream")
