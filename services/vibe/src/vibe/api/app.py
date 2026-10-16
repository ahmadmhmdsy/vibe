# services/vibe/src/vibe/api/app.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vibe.api.deps import require_principal
from vibe.api.errors import ApiError, ErrorCode, body
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventStore
from vibe.logging_setup import configure_logging
from vibe.maintenance import reap_dev_servers, render_reap
from vibe.store import SessionStore

logger = logging.getLogger(__name__)

#: Stored event types that mean "a turn was still going when the process died".
#: A healthy turn always ends with assistant/message, assistant/error or
#: turn/aborted -- and text_chunk/turn_complete are streamed, never stored (see
#: EventLog.next_seq) -- so a stored tail in this set is a crash signature and
#: not a heuristic.
_OPEN_TURN_TAILS = frozenset({"user/message", "tool_call", "tool_result"})

# How often the idle-dev-server reaper wakes up.
_REAP_INTERVAL_S = 60
# Methods that change state. A GET cannot be turned into a CSRF vector, so
# the Origin check only applies to these.
_STATE_CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _lifespan_factory(container: Container):
    """Build the app's startup/shutdown behaviour.

    A factory rather than a module-level function because the reaper and the
    shutdown sweep need the per-app registries, which only exist once the app
    has been composed.
    """
    executors = container.executors
    settings = container.settings
    store = container.store
    event_log = container.event_log
    runs = container.runs
    lifecycle = container.lifecycle

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Whether a turn is live is only true of this process's memory: there is
        # no "running" column to correct. What survives a crash is the event
        # log, so the log is what gets repaired, before anyone can ask and see a
        # spinner that can never end.
        closed = await reconcile_open_turns(store, event_log)
        if closed:
            logger.warning("startup: closed %d turn(s) left open by an earlier run", closed)
        # A deleted workspace is moved to .trash, never destroyed, so a mistaken
        # delete stays recoverable for the retention window. Sweep here as well
        # as on delete: a long-lived process that only deletes would otherwise
        # never run the sweep at all (BE-11). A failure here must not stop the
        # app from starting - the trash is housekeeping, not the product.
        try:
            reaped = await lifecycle.sweep_trash()
        except Exception:
            logger.exception("startup: the .trash sweep failed; continuing without it")
        else:
            if reaped:
                logger.info("startup: reaped %d expired trash entr(ies)", len(reaped))
        # A crash leaves the previous run's dev servers holding ports the next
        # run cannot reuse (AC-9). The pidfile only ever holds servers this app
        # started, and the reap verifies that a recorded pid's command line
        # mentions the recorded workspace before killing anything, so a recycled
        # pid is left alone and reported instead of being killed. Housekeeping
        # again: a failure here must not stop the app from starting.
        try:
            orphans = await asyncio.to_thread(reap_dev_servers, settings.workspace_dir)
        except Exception:
            logger.exception("startup: the dev-server reap failed; continuing without it")
        else:
            if orphans.reaped or orphans.dropped or orphans.kept or orphans.skipped:
                logger.info("startup: %s", render_reap(orphans))
        logger.info("vibe ready: workspace=%s", settings.workspace_dir)
        # P5: a non-loopback bind now requires a shared secret (config.py refuses
        # to build Settings without one), so this is not the footgun it once was.
        # Silence would still hide that the API left the loopback interface, so
        # say exactly what stands between it and the network.
        if settings.host not in ("127.0.0.1", "localhost", "::1"):
            # One placeholder, one argument. This call used to pass three
            # arguments for a single %s, and logging defers that mismatch to the
            # handler: the operator got a "--- Logging error ---" traceback
            # instead of the warning (BE-07).
            logger.warning(
                "VIBE_HOST=%s: bound beyond loopback; non-local peers must present the auth token.",
                settings.host,
            )
        reaper = asyncio.create_task(_reap_idle_dev_servers(executors, settings))
        try:
            yield
        finally:
            reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
            # Cancel the runs first: an in-flight turn is what would otherwise
            # keep writing into the stores we are about to close.
            aborted = runs.abort_all()
            if aborted:
                logger.info("shutdown: cancelling %d in-flight run(s)", aborted)
            # A dev server left running outlives the process that started it.
            stopping = len(executors)
            if stopping:
                logger.info("shutdown: stopping %d dev server(s)", stopping)
            for sid in list(executors):
                executor = executors.pop(sid, None)
                if executor is not None:
                    await executor.close()
            store.close()
            event_log.close()
            logger.info("vibe stopped")

    return lifespan


async def reconcile_open_turns(store: SessionStore, event_log: EventStore) -> int:
    """Close turns left open by a previous run; returns how many were closed.

    Only the last stored event of each session is read, so this stays cheap on a
    session with a long transcript.
    """
    closed = 0
    for session in await store.list_sessions():
        last_seq = event_log.last_seq(session.id)
        if last_seq <= 0:
            continue
        tail = await event_log.get(session.id, after_seq=last_seq - 1)
        if not tail or tail[-1].type not in _OPEN_TURN_TAILS:
            continue
        await event_log.append(session.id, "turn/aborted", {"reason": "the app stopped before this turn finished"})
        logger.info("startup: session %s had an open turn; marked it aborted", session.id)
        closed += 1
    return closed


async def _reap_idle_dev_servers(executors: dict, settings: Settings) -> None:
    """Stop dev servers that have been idle past the configured timeout.

    The timeout used to be parsed from the environment and then read by
    nothing, so a preview left open kept a `pnpm dev` process alive forever.
    """
    while True:
        await asyncio.sleep(_REAP_INTERVAL_S)
        for sid in list(executors):
            executor = executors.get(sid)
            if executor is None:
                continue
            try:
                await executor.stop_if_idle(settings.dev_server_idle_timeout_min)
            except Exception:
                # A reaper must never take the server down with it, but a bare
                # `pass` here made a broken preview indistinguishable from an
                # idle one (audit H5).
                logger.warning("idle-dev-server reap failed for session %s", sid, exc_info=True)


def _same_origin(stated: str, host: str | None, scheme: str) -> bool:
    """Is the stated Origin the same origin as this request's own Host?

    The Host header carries the authority but no scheme, so the scheme comes
    from the ASGI scope: an https page is not same-origin with an http request
    even on the same host and port. Compared by parsing, never by string
    prefix -- "http://127.0.0.1:73211" must not match a Host of
    "127.0.0.1:7321". A missing port takes the scheme's default, and the
    hostname comparison is case-insensitive.
    """
    if not host or scheme not in ("http", "https"):
        return False
    try:
        origin = urlsplit(stated)
        target = urlsplit(f"//{host}")
        origin_port = origin.port
        target_port = target.port
    except ValueError:
        # A malformed port (or IPv6 literal) is a refusal, never a 500.
        return False
    if origin.scheme != scheme:
        return False
    if origin.hostname is None or target.hostname is None:
        return False
    if origin.hostname.lower() != target.hostname.lower():
        return False
    default_port = 443 if scheme == "https" else 80
    return (origin_port or default_port) == (target_port or default_port)


class OriginGuard:
    """Refuses state-changing requests from an Origin we do not trust.
    Loopback auth cannot catch CSRF: a cross-site form POST from the user's
    own browser arrives from 127.0.0.1 and therefore looks local. The Origin
    header is the browser's own statement of which page sent the request, and
    only a page we trust sends one we allow -- so this is a second, independent
    control rather than a repeat of the authenticator.
    Two Origins are trusted: one on the configured allowlist (the cross-origin
    dev SPA, which stays reachable because VIBE_CORS_ORIGINS extends it), and
    one same-origin with the request's own Host. The second is what makes prod
    mode work: there the app serves the SPA itself, so the page's Origin is the
    server's own host:port and no fixed allowlist could name the port in
    advance. A foreign Origin is still refused, and reads are never checked.
    A request with no Origin header is allowed through. Loopback auth has
    already gated it, and non-browser clients (curl, a test) send none.
    """

    def __init__(self, app, allowed_origins: list[str]) -> None:
        self._app = app
        self._allowed = frozenset(o.rstrip("/") for o in allowed_origins)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["method"] not in _STATE_CHANGING:
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        origin = headers.get(b"origin")
        if origin is not None:
            stated = origin.decode("latin-1").rstrip("/")
            host = (headers.get(b"host") or b"").decode("latin-1")
            same_origin = _same_origin(stated, host, scope.get("scheme", ""))
            if stated not in self._allowed and not same_origin:
                logger.warning("refused a %s request from Origin %s", scope["method"], stated)
                await _error_response(ErrorCode.FORBIDDEN_ORIGIN, "origin not allowed", 403)(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _error_response(code: ErrorCode, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content=body(code, message))


async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return _error_response(exc.code, exc.message, exc.status)


# A route that still raises a bare HTTPException has to answer in the same
# shape, or it would be the one endpoint the frontend cannot parse.
_STATUS_CODES = {
    400: ErrorCode.VALIDATION_FAILED,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.RUN_IN_PROGRESS,
    422: ErrorCode.VALIDATION_FAILED,
}


async def _handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL)
    return _error_response(code, str(exc.detail), exc.status_code)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's own detail is a list of dicts, which is not something a UI can
    # show. The first location and reason is what a person needs to fix it.
    # 400, not FastAPI's default 422: every other rejection in this API is a
    # 400 in the {"error": {...}} shape, and a malformed body is a client
    # mistake the UI does not have to branch on separately.
    errors = exc.errors()
    if not errors:
        return _error_response(ErrorCode.VALIDATION_FAILED, "invalid request", 400)
    first = errors[0]
    # "body" is FastAPI's name for the request body itself; the useful part of
    # the location is the field path inside it. A non-object body has no field
    # path at all, so the reason stands alone.
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    reason = str(first.get("msg", "invalid request"))
    return _error_response(ErrorCode.VALIDATION_FAILED, f"{where}: {reason}" if where else reason, 400)


async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    # Log the real error, return a generic one: an exception message can carry
    # a filesystem path, an API key, or a provider's raw response body.
    logger.exception("unhandled error: %s", exc)
    return _error_response(ErrorCode.INTERNAL, "internal server error", 500)


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    # `python -m vibe` configures logging before calling us. When the app is
    # mounted by a host instead (uvicorn --factory, a test), nobody has, and
    # the records would fall through to the root logger's last-resort handler
    # and only surface at WARNING.
    if not logging.getLogger("vibe").handlers:
        configure_logging()

    # Keep the session index inside the workspace root so a single vibe
    # install owns both its workspaces and its session metadata.
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)

    # Every collaborator, composed once, before anything derives from it. Pass a
    # pre-built container to substitute seams (tests, embedded hosts).
    container = container or Container.build(settings)

    app = FastAPI(
        title="vibe",
        lifespan=_lifespan_factory(container),
    )
    # OriginGuard is added before CORSMiddleware so CORS is the outer layer and
    # the browser still sees its headers on a 403.
    app.add_middleware(OriginGuard, allowed_origins=settings.cors_origins)
    # CORS: the Vite dev server calls this API cross-origin. The port
    # varies (5173, or the next free one when busy), so the allowlist is
    # configurable via VIBE_CORS_ORIGINS (comma-separated).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # CORS exposes only a handful of simple response headers to JS by
        # default, so without this the browser hides the pagination count.
        expose_headers=["X-Total-Count"],
    )
    app.state.container = container

    # One response shape for every failure. FastAPI's defaults gave the frontend
    # three of them -- detail as a string, detail as a list, and a bare 500 --
    # and no code it could branch on.
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected)

    @app.get("/health")
    def health():
        # The resolved paths are the point: an un-expanded `VIBE_WORKSPACE_DIR`
        # used to make the same install look empty depending on the directory it
        # was launched from. This is the one place that shows where data
        # actually lives.
        return {
            "status": "ok",
            "workspace_dir": str(settings.workspace_dir),
            "sessions_db": str(settings.workspace_dir / "sessions.db"),
            "events_db": str(settings.workspace_dir / "events.db"),
        }

    @app.post("/admin/shutdown", dependencies=[Depends(require_principal)])
    async def shutdown(request: Request):
        """Ask the server to stop, for `stop.bat` and for a window you lost.

        POST rather than GET on purpose: OriginGuard only covers state-changing
        methods, and a GET would let any page the browser loads stop the app
        with an `<img src>`. It is behind the same authenticator as every other
        route, so only a caller on this machine can reach it.
        """
        request.app.state.shutdown_requested = True
        server = getattr(request.app.state, "uvicorn_server", None)
        if server is None:
            # No server object to steer (a test, or an embedded host): the flag
            # above is the whole signal, and the caller keeps running.
            logger.warning("shutdown requested, but this host has no uvicorn server to stop")
            return {"status": "shutting_down", "stopping": False}
        server.should_exit = True
        return {"status": "shutting_down", "stopping": True}

    from vibe.api.routes import approvals, catalog, chat, messages, preview, providers, sessions

    # Every router is mounted behind the authenticator, so the default is deny:
    # a route added tomorrow is protected without remembering to ask. /health
    # stays open above because it is a direct @app.get, not part of a router.
    for _router in (
        sessions.router,
        chat.router,
        catalog.router,
        providers.router,
        approvals.router,
        messages.router,
        preview.router,
    ):
        app.include_router(_router, dependencies=[Depends(require_principal)])

    # Production serves the built SPA from this same process, so the browser has
    # one origin and needs no VITE_API_URL. Mounted last so it can never shadow
    # an API route; in dev Vite owns the frontend and nothing is mounted.
    if settings.mode == "prod":
        from vibe.api.static import mount_spa

        mount_spa(app, settings.static_dir)

    return app
