# services/vibe/src/vibe/api/deps.py
"""Route-level access to the container.

Handlers used to take a `Request` and pull collaborators off `app.state` by
name. They now declare the container as a dependency, so what a route needs is
visible in its signature and FastAPI builds it per request.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from vibe.api.errors import ApiError, ErrorCode
from vibe.auth import Principal
from vibe.container import Container
from vibe.store import Session


def get_container(request: Request) -> Container:
    return request.app.state.container


# One name for "this route needs the app", reused by every handler.
App = Annotated[Container, Depends(get_container)]


async def require_principal(request: Request, deps: App) -> Principal:
    """The caller, or 401.

    Mounted as a router-level dependency rather than written into each
    handler, so a route added tomorrow is protected without remembering to
    ask. The default is deny: an authenticator that returns None refuses,
    and there is no path through a router that skips the check.
    """
    principal = await deps.authenticator.authenticate(request)
    if principal is None:
        raise ApiError(ErrorCode.UNAUTHENTICATED, "this API serves the local machine only")
    return principal


async def require_session(deps: Container, sid: str) -> Session:
    """Load a session, or 404.

    Every session-scoped route calls this first. It used to be inlined in each
    handler, so a route added without it failed on a missing session with a
    KeyError from the store rather than a 404 the client could act on.
    """
    session = await deps.store.get_session(sid)
    if session is None:
        raise ApiError(ErrorCode.SESSION_NOT_FOUND, "session not found")
    return session
