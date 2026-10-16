# services/vibe/src/vibe/auth.py
"""Who is asking, and how sure we are about them.

The app is local-first: one user, one machine. That is a trust decision, not an
oversight, and it is written down in README's Known gaps. This module is the
mechanism that decision hangs on.

`Authenticator` is the seam. `LoopbackAuthenticator` is the only
implementation today: a request that arrives from this machine is the local
user, and anything else is refused. It authenticates the *machine*, not a
person -- on a single-user machine those are the same thing, and the difference
only matters if the machine is ever shared.

A future `TokenAuthenticator` implements the same protocol. Swapping it is a
one-line change in `Container.build`; nothing else in the app knows which one
is installed, because routes ask for a `Principal` and never for a mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from starlette.requests import Request


@dataclass(frozen=True)
class Principal:
    """The authenticated caller.

    `id` is stable for the lifetime of the install. It is always "local" under
    loopback auth; a token authenticator would put a user id here, which is why
    the field exists rather than a boolean flag.
    """

    id: str
    name: str


# The identity of the single loopback user, in its one home. Every consumer
# reads it from the Principal that LoopbackAuthenticator returns -- a hard-coded
# "local" at a call site is what tests/test_seams.py refuses, because identity
# is the first thing that has to become per-user when this app is scaled.
LOOPBACK_OWNER_ID = "local"

# Peer addresses that mean "this machine". Starlette populates request.client
# from the socket, and TestClient -- which the whole suite runs through --
# reports "testclient" rather than a loopback address.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def _is_local(request: Request) -> bool:
    """True when the request came from this machine.

    `request.client is None` means the request never went through a real
    socket -- an in-process ASGI call. That is a trusted internal caller rather
    than a network peer, so it counts as local.
    """
    client = request.client
    if client is None:
        return True
    return client.host in _LOOPBACK_HOSTS


class Authenticator(Protocol):
    """Turns a request into a Principal, or None when it is not ours."""

    async def authenticate(self, request: Request) -> Principal | None: ...


class LoopbackAuthenticator:
    """Trusts every request that arrives from this machine.

    This is the whole of the auth story for a local single-user app, and it is
    deliberately small. It converts `VIBE_HOST=0.0.0.0` from a silent footgun
    into an inert setting: binding to every interface no longer exposes the API
    to the network, because a non-loopback peer is refused.

    It does **not** fix CSRF. A cross-site request from the user's own browser
    arrives from 127.0.0.1 and therefore looks local -- which is why the Origin
    check in api/app.py is a separate control and not a replacement for this.
    """

    async def authenticate(self, request: Request) -> Principal | None:
        if not _is_local(request):
            return None
        return Principal(id=LOOPBACK_OWNER_ID, name=LOOPBACK_OWNER_ID)
