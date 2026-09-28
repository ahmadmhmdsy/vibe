from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
from vibe.models import Message, AgentInput
from vibe.runtime.base import AgentContext
from vibe.events import Event

router = APIRouter()

@router.post("/sessions/{sid}/messages")
async def send_message(sid: str, body: dict, request: Request):
    store = request.app.state.store
    s = await store.get_session(sid)
    if not s: raise HTTPException(404, "not found")
    # append user message to log
    await request.app.state.event_log.append(sid, "user/message", {"content": body["content"]})
    # build context
    workspace = Path(request.app.state.settings.workspace_dir) / sid
    workspace.mkdir(parents=True, exist_ok=True)
    executor = request.app.state.get_executor(sid, workspace)
    ctx = AgentContext(session_id=sid, workspace_path=workspace, executor=executor,
                       event_bus=request.app.state.event_bus, store=store)
    inp = AgentInput(session_id=sid, messages=[Message(role="user", content=body["content"])], model=s.model_ref)
    # run agent, collecting events
    text_parts = []
    async for event in request.app.state.runtime.run(inp, ctx):
        if event.kind == "text_chunk":
            text_parts.append(event.data.get("text", ""))
            await request.app.state.event_bus.publish(sid, Event(session_id=sid, seq=0, type="text_chunk", payload=event.data))
        elif event.kind in ("tool_call", "tool_result"):
            seq = await request.app.state.event_log.append(sid, event.kind, event.data)
            await request.app.state.event_bus.publish(sid, Event(session_id=sid, seq=seq, type=event.kind, payload=event.data))
        elif event.kind == "turn_complete":
            await request.app.state.event_bus.publish(sid, Event(session_id=sid, seq=0, type="turn_complete", payload=event.data))
    # append assistant message
    content = "".join(text_parts)
    await request.app.state.event_log.append(sid, "assistant/message", {"content": content})
    return {"content": content}
