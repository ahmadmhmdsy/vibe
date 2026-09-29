# services/vibe/src/vibe/api/routes/preview.py
from fastapi import APIRouter, Request
from pathlib import Path

router = APIRouter()


def _workspace(request: Request, sid: str) -> Path:
    ws = Path(request.app.state.settings.workspace_dir) / sid
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@router.get("/sessions/{sid}/preview")
async def get_preview(sid: str, request: Request):
    ex = request.app.state.get_executor(sid, _workspace(request, sid))
    url = ex.dev_server_url
    return {"url": url, "is_running": url is not None}


@router.post("/sessions/{sid}/preview/run")
async def run_preview(sid: str, request: Request):
    ex = request.app.state.get_executor(sid, _workspace(request, sid))
    handle = await ex.start_dev_server()
    return {"url": handle.url, "is_running": True}


@router.post("/sessions/{sid}/preview/stop")
async def stop_preview(sid: str, request: Request):
    ex = request.app.state.get_executor(sid, _workspace(request, sid))
    await ex.stop_dev_server()
    return {"url": None, "is_running": False}
