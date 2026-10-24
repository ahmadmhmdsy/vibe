# tests/test_vcs.py
"""M8/C2: version control over a session's workspace.

Every test here runs against a real repository in a tmp dir. A version-control
seam stubbed out would only prove the stub: what has to hold is that a workspace
which is *not* a repository is not mistaken for one (a commit in the wrong
history is unrecoverable), that the app never pushes, and that a client-supplied
branch name cannot become a git option.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from vibe.vcs import GitVcs, VcsError, build_vcs

_MODEL = {"provider_id": "openai", "model_id": "gpt-4o"}

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")

#: A commit needs an identity; without this the test would depend on whatever
#: the machine running it happens to have configured globally.
_IDENTITY = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    return path


def _git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=path, check=True, capture_output=True, text=True, env={**os.environ, **_IDENTITY}
    )


# --- not a repository, and not one by accident -----------------------------


async def test_a_plain_directory_is_not_a_repository_and_never_throws(tmp_path):
    vcs = GitVcs(tmp_path)

    status = await vcs.status()

    assert status.is_repo is False
    assert status.files == []
    assert status.branch is None
    assert await vcs.log() == []
    # The actions that need a repository say so instead of failing on git's exit
    # code, which a UI cannot act on.
    with pytest.raises(VcsError, match="not a git repository"):
        await vcs.commit("nope")
    with pytest.raises(VcsError, match="not a git repository"):
        await vcs.diff()


async def test_a_workspace_inside_someone_elses_repository_is_not_this_repo(tmp_path):
    """git's own `rev-parse` answers for any enclosing repository.

    Trusting it would put this workspace on the outer repository's branch, list
    its changes, and -- worst of the three -- write a commit into a history the
    user never offered us.
    """
    outer = _repo(tmp_path / "outer")
    inner = outer / "nested"
    inner.mkdir()

    status = await GitVcs(inner).status()

    assert status.is_repo is False


# --- init -----------------------------------------------------------------


async def test_init_makes_a_repository_and_ignores_the_files_that_never_belong(tmp_path):
    (tmp_path / "app.ts").write_text("x", encoding="utf-8")
    vcs = GitVcs(tmp_path)

    await vcs.init()

    assert (await vcs.status()).is_repo is True
    # A generated app vendors node_modules and may keep a .env; neither belongs
    # in the first commit of a repository this app created.
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "node_modules" in ignore
    assert ".env" in ignore


async def test_init_never_overwrites_an_ignore_file_that_is_already_there(tmp_path):
    (tmp_path / ".gitignore").write_text("keep-me\n", encoding="utf-8")

    await GitVcs(tmp_path).init()

    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == "keep-me\n"


async def test_init_on_a_repository_that_already_exists_changes_nothing(tmp_path):
    repo = _repo(tmp_path)
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")

    await GitVcs(repo).init()

    # Nothing was written by us: the repository already had its own rules.
    assert not (repo / ".gitignore").exists()


# --- commit ---------------------------------------------------------------


async def test_a_commit_returns_a_sha_and_leaves_a_clean_workspace(tmp_path):
    vcs = GitVcs(_repo(tmp_path))
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")

    sha = await vcs.commit("first")

    assert sha and len(sha) >= 7
    assert (await vcs.status()).files == []
    commits = await vcs.log()
    assert [c.subject for c in commits] == ["first"]


async def test_committing_nothing_is_not_an_error(tmp_path):
    vcs = GitVcs(_repo(tmp_path))
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    assert await vcs.commit("first") is not None

    # Nothing has changed since: the panel's button races the agent, so this is
    # an empty answer, not a failure to report.
    assert await vcs.commit("second") is None


async def test_a_commit_needs_a_message(tmp_path):
    with pytest.raises(VcsError, match="needs a message"):
        await GitVcs(_repo(tmp_path)).commit("   ")


async def test_a_commit_works_on_a_machine_with_no_git_identity(tmp_path):
    """git refuses to commit without a name and an email.

    A fresh machine has neither, so the app supplies one -- only when the
    repository has none, so a user's own identity is never overridden.
    """
    repo = _repo(tmp_path)
    _git(repo, "config", "user.email", "")
    _git(repo, "config", "user.name", "")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")

    sha = await GitVcs(repo).commit("first")

    assert sha is not None
    author = _git(repo, "log", "-1", "--pretty=%an <%ae>").stdout.strip()
    assert author == "vibe <vibe@localhost>"


async def test_a_users_own_identity_is_never_overridden(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "config", "user.email", "me@example.com")
    _git(repo, "config", "user.name", "Me")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")

    await GitVcs(repo).commit("first")

    assert _git(repo, "log", "-1", "--pretty=%an <%ae>").stdout.strip() == "Me <me@example.com>"


async def test_a_commit_message_that_looks_like_an_option_is_still_a_message(tmp_path):
    """The message is an argv value, never a shell string, so it cannot become
    a command -- and git reads it as the value of -m rather than as an option."""
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")

    await GitVcs(repo).commit("--amend --no-edit")

    assert _git(repo, "log", "-1", "--pretty=%s").stdout.strip() == "--amend --no-edit"


# --- branch ---------------------------------------------------------------


async def test_switching_creates_and_moves_to_a_new_branch(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    vcs = GitVcs(repo)
    await vcs.commit("first")
    before = await vcs.branch()

    assert await vcs.switch("feature", create=True) == "feature"
    assert await vcs.branch() == "feature"
    assert before != "feature"


@pytest.mark.parametrize("name", ["-x", "a b", "x..y", "", "x~1", "x^", "x:y"])
async def test_a_branch_name_that_could_be_an_option_or_is_invalid_is_refused(tmp_path, name):
    vcs = GitVcs(_repo(tmp_path))
    with pytest.raises(VcsError, match="not a usable branch name"):
        await vcs.switch(name, create=True)


# --- diff -----------------------------------------------------------------


async def test_the_diff_shows_a_change_and_separates_staged_from_worktree(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    vcs = GitVcs(repo)
    await vcs.commit("first")

    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    worktree = await vcs.diff()
    assert "-one" in worktree and "+two" in worktree
    assert await vcs.diff(staged=True) == ""

    _git(repo, "add", ".")
    assert "+two" in await vcs.diff(staged=True)
    assert await vcs.diff() == ""


async def test_a_diff_can_be_narrowed_to_one_file(tmp_path):
    repo = _repo(tmp_path)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    (repo / "b.txt").write_text("one\n", encoding="utf-8")
    vcs = GitVcs(repo)
    await vcs.commit("first")
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    (repo / "b.txt").write_text("two\n", encoding="utf-8")

    text = await vcs.diff(path="a.txt")

    assert "a.txt" in text
    assert "b.txt" not in text


# --- through the API ------------------------------------------------------


def _template_session(client) -> str:
    """A workspace with files in it, which is what a commit needs."""
    resp = client.post("/sessions", json={"model": _MODEL, "source": {"kind": "template"}})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_the_status_route_says_a_fresh_workspace_is_not_a_repository(client):
    sid = _template_session(client)

    body = client.get(f"/sessions/{sid}/vcs").json()

    assert body["is_repo"] is False
    assert body["branch"] is None
    assert body["files"] == []


def test_initialising_then_committing_from_the_api_leaves_a_clean_workspace(client):
    sid = _template_session(client)

    init = client.post(f"/sessions/{sid}/vcs/init")
    assert init.status_code == 201, init.text
    branch = init.json()["branch"]

    dirty = client.get(f"/sessions/{sid}/vcs").json()
    assert dirty["is_repo"] is True
    assert dirty["branch"] == branch
    assert [f["path"] for f in dirty["files"]] == [
        ".gitignore",
        "AI_RULES.md",
        "index.html",
        "package.json",
        "src/App.tsx",
        "src/main.tsx",
        "tsconfig.json",
        "vite.config.ts",
    ]

    commit = client.post(f"/sessions/{sid}/vcs/commit", json={"message": "scaffold"})
    assert commit.status_code == 201, commit.text
    assert commit.json()["committed"] is True
    assert commit.json()["sha"]

    assert client.get(f"/sessions/{sid}/vcs").json()["files"] == []
    log = client.get(f"/sessions/{sid}/vcs/log").json()
    assert [c["subject"] for c in log] == ["scaffold"]


def test_committing_an_unchanged_workspace_answers_committed_false(client):
    sid = _template_session(client)
    client.post(f"/sessions/{sid}/vcs/init")
    assert client.post(f"/sessions/{sid}/vcs/commit", json={"message": "one"}).json()["committed"] is True

    again = client.post(f"/sessions/{sid}/vcs/commit", json={"message": "two"})

    assert again.status_code == 201
    assert again.json() == {"sha": None, "committed": False}


def test_a_commit_without_a_message_is_a_validation_failure(client):
    sid = _template_session(client)
    client.post(f"/sessions/{sid}/vcs/init")

    resp = client.post(f"/sessions/{sid}/vcs/commit", json={"message": ""})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_failed"


def test_a_branch_can_be_created_from_the_api_and_a_bad_name_is_a_400(client):
    sid = _template_session(client)
    client.post(f"/sessions/{sid}/vcs/init")
    client.post(f"/sessions/{sid}/vcs/commit", json={"message": "one"})

    made = client.post(f"/sessions/{sid}/vcs/branch", json={"name": "feature", "create": True})
    assert made.status_code == 201, made.text
    assert made.json()["branch"] == "feature"
    assert client.get(f"/sessions/{sid}/vcs").json()["branch"] == "feature"

    bad = client.post(f"/sessions/{sid}/vcs/branch", json={"name": "--upload-pack=x", "create": True})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "validation_failed"


def test_initialise_refuses_a_workspace_that_is_not_there(client, app, container):
    """A session whose workspace was removed by hand is a 400, not a 500."""
    sid = client.post("/sessions", json={"model": _MODEL}).json()["id"]
    shutil.rmtree(container.session_service.workspace_path(sid))

    resp = client.post(f"/sessions/{sid}/vcs/init")

    assert resp.status_code == 400
    assert resp.json()["error"]["message"] == "this session has no workspace to initialise"


def test_the_vcs_routes_are_scoped_to_a_session_that_exists(client):
    assert client.get("/sessions/nope/vcs").status_code == 404
    assert client.get("/sessions/nope/vcs/log").status_code == 404
    assert client.get("/sessions/nope/vcs/diff").status_code == 404
    assert client.post("/sessions/nope/vcs/init").status_code == 404
    assert client.post("/sessions/nope/vcs/commit", json={"message": "x"}).status_code == 404
    assert client.post("/sessions/nope/vcs/branch", json={"name": "x"}).status_code == 404


def test_a_staged_truncated_diff_is_reported_as_truncated(client, container):
    sid = _template_session(client)
    client.post(f"/sessions/{sid}/vcs/init")
    ws = container.session_service.workspace_path(sid)
    big = ws / "big.txt"
    big.write_text("".join(f"line {i} of a deliberately large file\n" for i in range(8000)), encoding="utf-8")
    _git(ws, "add", "big.txt")

    body = client.get(f"/sessions/{sid}/vcs/diff", params={"staged": True, "path": "big.txt"}).json()

    assert body["truncated"] is True
    assert "truncated" in body["diff"]


def test_build_vcs_names_the_provider(tmp_path):
    """One place turns a workspace into a provider, so the routes name no git."""
    assert build_vcs(tmp_path).__class__ is GitVcs
