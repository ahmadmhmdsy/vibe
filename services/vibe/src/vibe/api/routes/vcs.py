# services/vibe/src/vibe/api/routes/vcs.py
"""Source control for a session's workspace (M8/C2).

Every route here is scoped to one session's workspace and none of them talks to
a remote: pushing is a user action in their own terminal, and a local-first tool
does not silently publish anything.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Request

from vibe.api.deps import App, Owner, require_session
from vibe.api.errors import ApiError, ErrorCode
from vibe.api.schemas import BranchIn, CommitIn
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.vcs import MAX_DIFF, VcsError, build_vcs

router = APIRouter()


async def _guard(coro):
    """Run one version-control call, turning a refusal into a 400.

    "This workspace is not a repository" and "git is not installed" are things
    the caller can act on, not crashes -- the same treatment `ProjectError` gets
    on the create route.
    """
    try:
        return await coro
    except VcsError as exc:
        raise ApiError(ErrorCode.VALIDATION_FAILED, str(exc)) from exc


def _payload(files) -> list[dict]:
    # `staged` is derived from the porcelain code rather than stored, so it is
    # named here where the response shape is decided.
    return [{"path": f.path, "status": f.status, "staged": f.staged} for f in files]


@router.get("/sessions/{sid}/vcs")
async def vcs_status(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    status = await _guard(build_vcs(deps.session_service.workspace_path(sid)).status())
    # Not a repository is an answer, not a 404: the panel offers to create one.
    return {"is_repo": status.is_repo, "branch": status.branch, "files": _payload(status.files)}


@router.post("/sessions/{sid}/vcs/init", status_code=201)
async def vcs_init(sid: str, request: Request, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    vcs = build_vcs(deps.session_service.workspace_path(sid))
    await _guard(vcs.init())
    return {"branch": await _guard(vcs.branch())}


@router.get("/sessions/{sid}/vcs/diff")
async def vcs_diff(
    sid: str,
    request: Request,
    deps: App,
    path: str | None = None,
    staged: bool = False,
    owner: Owner = LOOPBACK_OWNER_ID,
):
    await require_session(deps, sid, owner)
    vcs = build_vcs(deps.session_service.workspace_path(sid))
    text = await _guard(vcs.diff(path=path, staged=staged))
    # The marker alone is not enough: the client should be able to say so in the
    # UI without matching on prose.
    return {"diff": text, "truncated": len(text) > MAX_DIFF}


@router.post("/sessions/{sid}/vcs/commit", status_code=201)
async def vcs_commit(sid: str, request: Request, body: CommitIn, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    sha = await _guard(build_vcs(deps.session_service.workspace_path(sid)).commit(body.message))
    # `committed: false` is the race with the agent writing nothing new, not a
    # failure: the panel says "nothing to commit" instead of showing an error.
    return {"sha": sha, "committed": sha is not None}


@router.get("/sessions/{sid}/vcs/log")
async def vcs_log(sid: str, request: Request, deps: App, limit: int = 20, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    commits = await _guard(build_vcs(deps.session_service.workspace_path(sid)).log(limit))
    return [asdict(c) for c in commits]


@router.post("/sessions/{sid}/vcs/branch", status_code=201)
async def vcs_branch(sid: str, request: Request, body: BranchIn, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    await require_session(deps, sid, owner)
    vcs = build_vcs(deps.session_service.workspace_path(sid))
    name = await _guard(vcs.switch(body.name, create=body.create))
    return {"branch": name}
