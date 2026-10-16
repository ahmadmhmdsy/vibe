# services/vibe/src/vibe/api/routes/preview.py
from fastapi import APIRouter, Request

from vibe.api.deps import App, Owner, require_session
from vibe.auth import LOOPBACK_OWNER_ID

router = APIRouter()


@router.get("/sessions/{sid}/preview")
async def get_preview(sid: str, request: Request, deps: App,
                       owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    ex = deps.get_executor(sid, deps.session_service.ensure_workspace(sid), owner_id=owner)
    url = ex.dev_server_url
    return {"url": url, "is_running": url is not None}


@router.post("/sessions/{sid}/preview/run")
async def run_preview(sid: str, request: Request, deps: App,
                      owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    ex = deps.get_executor(sid, deps.session_service.ensure_workspace(sid), owner_id=owner)
    handle = await ex.start_dev_server()
    return {"url": handle.url, "is_running": True}


@router.post("/sessions/{sid}/preview/stop")
async def stop_preview(sid: str, request: Request, deps: App,
                       owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    ex = deps.get_executor(sid, deps.session_service.ensure_workspace(sid), owner_id=owner)
    await ex.stop_dev_server()
    return {"url": None, "is_running": False}
