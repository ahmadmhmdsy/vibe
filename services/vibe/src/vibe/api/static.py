# services/vibe/src/vibe/api/static.py
"""Serve the built SPA from the API process (the production single-port mode).

In development Vite owns the frontend and calls this API cross-origin. In
production there is no Vite: this process serves both, so the browser sees one
origin, one port and no CORS, and `VITE_API_URL` stays unset (see
apps/vibe/src/lib/api.ts).

Mounting `StaticFiles(directory=dist)` on its own is not enough. It answers a
deep link such as `/sessions/abc` with a 404, because the path is a client
route and no such file exists -- refreshing a page would look like the app had
lost its data. Every path that is not a real file therefore returns the shell
and lets the client router decide.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from vibe.api.errors import ErrorCode, body

#: Vite fingerprints the filenames it emits, so an asset URL can never change
#: meaning and may be cached for as long as the browser is willing.
_IMMUTABLE = "public, max-age=31536000, immutable"
#: index.html is the only file that names those hashed assets, so it must be
#: revalidated: a stale one would point at assets a new build deleted.
_NO_CACHE = "no-cache"

#: The API's own namespace. A catch-all that answered these with the shell would
#: turn every mistyped API call into a 200 that the client cannot parse.
_API_PREFIX = "api"


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    """Serve `dist_dir` at `/`, with the SPA fallback.

    Raises RuntimeError when the build is missing: starting production mode
    without a build used to be a blank page with no explanation, and an empty
    page is the one failure a user cannot debug.
    """
    if not (dist_dir / "index.html").is_file():
        raise RuntimeError(
            f"the built frontend is missing at {dist_dir} - run `pnpm run build`"
            " (or `pnpm --dir apps/vibe run build`) before serving production mode,"
            " or start in dev mode (VIBE_MODE=dev)"
        )

    index = dist_dir / "index.html"
    root = dist_dir.resolve()

    # Deliberately one route rather than a StaticFiles mount: the mount answers
    # /assets itself and ignores the cache header a mount cannot be given, and a
    # missing asset under it falls through to whatever is mounted next.
    #
    # No response-model annotation either: FastAPI would try to build one from
    # the union of the two response types and refuse at import time.
    # GET and HEAD: a HEAD that answered 405 is how a monitoring check or a
    # link preview decides the app is broken. FileResponse answers HEAD with
    # the same headers and no body.
    @app.api_route("/{client_path:path}", methods=["GET", "HEAD"], include_in_schema=False, response_model=None)
    async def spa(client_path: str):
        if client_path == _API_PREFIX or client_path.startswith(_API_PREFIX + "/"):
            return JSONResponse(status_code=404, content=body(ErrorCode.NOT_FOUND, f"no API route at /{client_path}"))
        # The path is user input. A leading "../" must not be able to read a file
        # outside the build, so the resolved candidate has to still sit inside it.
        candidate = (dist_dir / client_path).resolve() if client_path else None
        inside = candidate is not None and root in candidate.parents
        if client_path.startswith("assets/"):
            if inside and candidate.is_file():
                return FileResponse(candidate, headers={"Cache-Control": _IMMUTABLE})
            # A build that lost an asset must say so. Returning the shell would
            # make a half-built app look like a working one.
            return JSONResponse(status_code=404, content=body(ErrorCode.NOT_FOUND, f"no asset at /{client_path}"))
        if inside and candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": _NO_CACHE})
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})
