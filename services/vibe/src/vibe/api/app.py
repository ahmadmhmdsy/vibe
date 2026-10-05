# services/vibe/src/vibe/api/app.py
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vibe.api.deps import require_principal
from vibe.api.errors import ApiError, ErrorCode, body
from vibe.config import Settings
from vibe.container import Container
from vibe.logging_setup import configure_logging

logger = logging.getLogger(__name__)

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

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("vibe ready: workspace=%s", settings.workspace_dir)
        # Loopback auth makes a non-loopback bind inert rather than dangerous,
        # but silence about it would be its own kind of footgun: the day the API
        # is exposed, the person who exposed it should be told what stands between
        # it and the network.
        if settings.host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(
                "VIBE_HOST=%s: bound beyond loopback; loopback auth still refuses non-local peers,",
                " but every local process can reach this API.",
                settings.host,
            )
        reaper = asyncio.create_task(_reap_idle_dev_servers(executors, settings))
        try:
            yield
        finally:
            reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
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


class OriginGuard:
    """Refuses state-changing requests from an Origin we do not trust.
    Loopback auth cannot catch CSRF: a cross-site form POST from the user's
    own browser arrives from 127.0.0.1 and therefore looks local. The Origin
    header is the browser's own statement of which page sent the request, and
    only a page we serve sends one we allow -- so this is a second, independent
    control rather than a repeat of the authenticator.
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
            if stated not in self._allowed:
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
    errors = exc.errors()
    if not errors:
        return _error_response(ErrorCode.VALIDATION_FAILED, "invalid request", 422)
    first = errors[0]
    where = ".".join(str(p) for p in first.get("loc", ()))
    reason = str(first.get("msg", "invalid request"))
    return _error_response(ErrorCode.VALIDATION_FAILED, f"{where}: {reason}" if where else reason, 422)


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

    from vibe.api.routes import approvals, catalog, chat, messages, preview, providers, sessions
    # Every router is mounted behind the authenticator, so the default is deny:
    # a route added tomorrow is protected without remembering to ask. /health
    # stays open above because it is a direct @app.get, not part of a router.
    for _router in (sessions.router, chat.router, catalog.router, providers.router,
                    approvals.router, messages.router, preview.router):
        app.include_router(_router, dependencies=[Depends(require_principal)])

    return app
