# services/vibe/src/vibe/api/deps.py
"""Route-level access to the container, and the one place identity enters.

Handlers used to take a `Request` and pull collaborators off `app.state` by
name. They now declare the container as a dependency, so what a route needs is
visible in its signature and FastAPI builds it per request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from vibe.api.errors import ApiError, ErrorCode
from vibe.auth import LOOPBACK_OWNER_ID, Principal
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


#: The authenticated caller, as a dependency.
PrincipalDep = Annotated[Principal, Depends(require_principal)]


async def current_owner(principal: PrincipalDep) -> str:
    """The owner every session-scoped read, registry key and delete uses.

    This is the single point where identity enters a request. A route declares
    `owner: Owner` and passes it down; no route spells an owner itself. Today
    the loopback authenticator returns one owner, so this is the identity the
    app has always had -- but it is now *read* rather than assumed, so an
    authenticator that returns a real user needs no change below it.
    """
    return principal.id


#: The current owner id, as a dependency.
Owner = Annotated[str, Depends(current_owner)]


async def require_session(deps: Container, sid: str, owner_id: str = LOOPBACK_OWNER_ID) -> Session:
    """Load one of this owner's sessions, or 404.

    Every session-scoped route calls this first. It used to be inlined in each
    handler, so a route added without it failed on a missing session with a
    KeyError from the store rather than a 404 the client could act on.

    The owner defaults to the loopback owner so a direct call from a test or a
    script keeps working; a request reaches here through `Owner`, which reads
    the principal. A session belonging to someone else is indistinguishable from
    one that does not exist, which is the answer that leaks nothing.
    """
    session = await deps.store.get_session(sid, owner_id)
    if session is None:
        raise ApiError(ErrorCode.SESSION_NOT_FOUND, "session not found")
    # The row is the only place an imported session's workspace path is written
    # down, so it is handed to the service here -- the one point every
    # session-scoped route passes through. The path itself is read synchronously
    # later, on the file-read hot path, where a store round trip per call would
    # be pure overhead for a value already in hand.
    deps.session_service.remember(sid, session.workspace_path)
    return session
