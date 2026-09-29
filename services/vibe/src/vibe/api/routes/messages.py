# services/vibe/src/vibe/api/routes/messages.py
from fastapi import APIRouter, Request

router = APIRouter()

_MESSAGE_TYPES = {"user/message": "user", "assistant/message": "assistant"}


@router.get("/sessions/{sid}/messages")
async def get_messages(sid: str, request: Request):
    """Reconstruct chat history for a session from the EventLog.

    The log is the source of truth ("model-visible means logged"); this
    endpoint derives the ordered user/assistant message list from it.
    """
    events = await request.app.state.event_log.get(sid)
    messages = []
    for e in events:
        role = _MESSAGE_TYPES.get(e.type)
        if role is None:
            continue
        content = e.payload.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    return messages
