# services/vibe/src/vibe/api/routes/messages.py
from fastapi import APIRouter, Query, Response

from vibe.api.deps import App, require_session

router = APIRouter()

# Bounds exist so one request cannot ask the server to materialise an unbounded
# transcript. 200 is a screenful and then some; 1000 is the ceiling a client may
# raise it to.
_DEFAULT_LIMIT = 200
_MAX_LIMIT = 1000


@router.get("/sessions/{sid}/messages")
async def get_messages(
    sid: str,
    response: Response,
    deps: App,
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Reconstruct chat history for a session from the EventLog.

    The log is the source of truth ("model-visible means logged"); this
    endpoint derives the ordered user/assistant message list from it.

    `offset` counts back from the most recent message, so a chat client pages
    backwards: offset 0 is the latest page, offset `limit` the one before it.
    """
    await require_session(deps, sid)
    page = await deps.message_service.page(sid, limit=limit, offset=offset)
    # The count travels in a header so this endpoint keeps returning the same
    # bare array as every other collection in the API.
    response.headers["X-Total-Count"] = str(page.total)
    # The service returns Message objects; the wire format is the route's call,
    # so a field added to Message does not silently appear in the response.
    return [{"role": m.role, "content": m.content} for m in page.messages]
