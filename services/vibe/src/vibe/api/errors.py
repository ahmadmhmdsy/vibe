# services/vibe/src/vibe/api/errors.py
"""A machine-readable error contract.

Routes used to raise bare HTTPExceptions, so the only thing a client could do
with a failure was print its detail string. Every error the frontend might
reason about now carries a stable code it can branch on, and the response body
has one shape regardless of which layer raised it:

    {"error": {"code": "session_not_found", "message": "session not found"}}

The status code still matters — it is what a proxy and the browser see — but
the code is the part that is safe to switch on.
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable identifiers. Renaming one is a breaking API change."""

    # The session id in the path does not name a session.
    SESSION_NOT_FOUND = "session_not_found"
    # Some other named resource does not exist.
    NOT_FOUND = "not_found"
    # A turn is already running for this session; wait for it or abort it.
    RUN_IN_PROGRESS = "run_in_progress"
    # The request conflicts with existing state, such as a duplicate name.
    CONFLICT = "conflict"
    # The session's own files are still open in another program, so the session
    # cannot be finished off yet. Retrying after closing it will work.
    WORKSPACE_BUSY = "workspace_busy"
    # The request was understood but its contents were not usable.
    VALIDATION_FAILED = "validation_failed"
    # The selected provider has no credentials, or is not one we can build.
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    # The request did not come from this machine.
    UNAUTHENTICATED = "unauthenticated"
    # A state-changing request carried an Origin we do not trust.
    FORBIDDEN_ORIGIN = "forbidden_origin"
    # Anything unhandled. The message is deliberately generic.
    INTERNAL = "internal"


# The status a code answers with unless a call site overrides it. Keeping the
# mapping here means a route states the code — the part a client branches on —
# and the transport detail follows from it instead of being repeated.
_DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.SESSION_NOT_FOUND: 404,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RUN_IN_PROGRESS: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.WORKSPACE_BUSY: 409,
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.PROVIDER_NOT_CONFIGURED: 400,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.FORBIDDEN_ORIGIN: 403,
    ErrorCode.INTERNAL: 500,
}


class ApiError(Exception):
    """An error a client can branch on.

    Subclasses nothing: api/app.py installs the handler that turns it into a
    response, so route code never shapes one itself.
    """

    def __init__(self, code: ErrorCode, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status if status is not None else _DEFAULT_STATUS[code]


def body(code: ErrorCode, message: str) -> dict:
    """The single response shape for every error, from every layer."""
    return {"error": {"code": code.value, "message": message}}
