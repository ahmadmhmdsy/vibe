# services/vibe/src/vibe/vcs.py
"""Version control for a session's workspace (M8/C2).

The seam is deliberately small: `status`, `diff`, `commit`, `branch`, `log`.
`GitVcs` is the only implementation, because git is the only system anybody
asked for -- a second one is not worth an abstraction until it exists. What a
second provider *would* need is already isolated here: the workspace is the
only input, the results are plain dataclasses, and no route knows a git command.

Local-first rules that shape this module:

- Nothing pushes. A remote is a user action; the app has no remote of its own.
- Every command is argv, never a shell, and every argument that comes from a
  client (a branch name, a commit message) is validated before it is passed --
  a value starting with "-" would otherwise be read as git's own option.
- A workspace that is not a repository is not an error: `status()` says so, and
  only the actions that need a repository refuse.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

#: Long enough for a big install's first commit on a cold disk, short enough
#: that a hung git (a credential prompt on a remote, a locked index) cannot hold
#: a request open forever.
_GIT_TIMEOUT = 30

#: A diff is meant to be read. Beyond this the response is a mirror of the
#: filesystem, and the client truncates the render anyway.
MAX_DIFF = 200_000

#: Branch names git would accept but we do not: the pattern rejects a leading
#: "-" (an option in disguise), spaces, "~^:?*[\\", and "..".
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")

#: Used only when the repository has no identity of its own, since git refuses
#: to commit without one ("Please tell me who you are"). An identity the user
#: configured is never overridden.
_FALLBACK_IDENTITY = ("-c", "user.name=vibe", "-c", "user.email=vibe@localhost")

#: Written when *we* create a repository. A generated app vendors node_modules
#: and may hold secrets in .env, and neither belongs in the first commit.
_INITIAL_GITIGNORE = "node_modules/\ndist/\n.env\n.env.local\n"

#: Untracked files are listed one by one rather than collapsed into their
#: directory: a panel row has to name something it can diff and commit. The
#: ceiling is a payload bound for a repository with no .gitignore, where
#: node_modules alone is tens of thousands of paths.
#: ponytail: one flat cap. Page the listing if a real workspace ever reaches it.
_MAX_STATUS_FILES = 2000


class VcsError(RuntimeError):
    """A version-control action the caller can fix and retry."""


@dataclass(frozen=True)
class VcsFile:
    """One changed path. `status` is git's two-letter porcelain code."""

    path: str
    status: str

    @property
    def staged(self) -> bool:
        # Porcelain column 1 is the index, column 2 the worktree; "?" and " "
        # in column 1 both mean "nothing staged for this path".
        return self.status[:1] not in (" ", "?")


@dataclass(frozen=True)
class VcsCommit:
    sha: str
    subject: str
    author: str
    date: str


@dataclass(frozen=True)
class VcsStatus:
    """What the panel renders. Not a repository is an answer, not a failure."""

    is_repo: bool
    branch: str | None = None
    files: list[VcsFile] = field(default_factory=list)


class Vcs(Protocol):
    """The seam. A workspace in, plain data out."""

    def status(self) -> VcsStatus: ...
    def diff(self, *, path: str | None = None, staged: bool = False) -> str: ...
    def log(self, limit: int = 20) -> list[VcsCommit]: ...
    def commit(self, message: str) -> str | None: ...
    def branch(self) -> str | None: ...
    def switch(self, name: str, *, create: bool = False) -> str: ...
    def init(self) -> None: ...


def _git_exe() -> str:
    # Windows: git is git.exe, but look it up for the same reason pnpm is looked
    # up -- a shim on PATH is not always launchable by its bare name.
    return shutil.which("git") or "git"


class GitVcs:
    """git, run in one workspace.

    Every method is async: a route must not block the loop on a 30-second git
    call, and `git add` on a large tree is not instant.
    """

    def __init__(self, workspace: Path, *, timeout: int = _GIT_TIMEOUT) -> None:
        self._workspace = Path(workspace).resolve()
        self._timeout = timeout
        self._git = _git_exe()

    # --- plumbing -----------------------------------------------------------

    async def _run(self, *args: str, check: bool = True) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._git,
                *args,
                cwd=self._workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            raise VcsError("git is not installed, or not on PATH") from exc
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except TimeoutError:
            proc.kill()
            raise VcsError(f"git {args[0]} timed out after {self._timeout}s") from None
        text = out.decode(errors="replace")
        if check and proc.returncode != 0:
            # git's own first line is the specific cause ("not a git repository",
            # "a branch named X already exists"); an exit code is not.
            detail = text.strip().splitlines()
            raise VcsError(detail[0] if detail else f"git {args[0]} failed ({proc.returncode})")
        return proc.returncode or 0, text

    async def _is_repo(self) -> bool:
        """True only when *this* directory is the repository root.

        `rev-parse` alone answers for any enclosing repository, so a workspace
        sitting inside someone else's checkout would report their branch and
        their changes, and a commit here would land in their history. Comparing
        the toplevel is what makes "this workspace is a repo" mean that.
        """
        if not self._workspace.is_dir():
            return False
        code, out = await self._run("rev-parse", "--show-toplevel", check=False)
        if code != 0:
            return False
        try:
            return Path(out.strip()).resolve() == self._workspace
        except OSError:
            return False

    async def _has_identity(self) -> bool:
        _, email = await self._run("config", "user.email", check=False)
        return bool(email.strip())

    # --- the seam -----------------------------------------------------------

    async def status(self) -> VcsStatus:
        if not await self._is_repo():
            return VcsStatus(is_repo=False)
        return VcsStatus(is_repo=True, branch=await self.branch(), files=await self._files())

    async def _files(self) -> list[VcsFile]:
        _, out = await self._run("status", "--porcelain", "--untracked-files=all")
        files: list[VcsFile] = []
        for line in out.splitlines()[:_MAX_STATUS_FILES]:
            if len(line) < 4:
                continue
            path = line[3:]
            # A rename reports "old -> new"; the new path is the one that exists.
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.append(VcsFile(path=path.strip(), status=line[:2]))
        return files

    async def diff(self, *, path: str | None = None, staged: bool = False) -> str:
        if not await self._is_repo():
            raise VcsError("this workspace is not a git repository")
        args = ["diff"]
        if staged:
            args.append("--cached")
        if path:
            # "--" ends option parsing, so a path is never read as a flag.
            args.extend(["--", path])
        _, out = await self._run(*args)
        if len(out) > MAX_DIFF:
            return out[:MAX_DIFF] + "\n… diff truncated; narrow it to one file.\n"
        return out

    async def log(self, limit: int = 20) -> list[VcsCommit]:
        if not await self._is_repo():
            return []
        # A field separator rather than a delimiter per line: a commit subject
        # may contain anything, newlines included.
        code, out = await self._run(
            "log",
            f"-n{max(1, min(limit, 200))}",
            "--pretty=format:%H%x1f%s%x1f%an%x1f%aI",
            check=False,
        )
        if code != 0:
            # The usual cause is an empty repository: git log on a repository
            # with no commits exits 128. No commits is an empty list.
            return []
        commits: list[VcsCommit] = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 4:
                commits.append(VcsCommit(sha=parts[0], subject=parts[1], author=parts[2], date=parts[3]))
        return commits

    async def commit(self, message: str) -> str | None:
        """Commit every change and return the short sha, or None if there was
        nothing to commit.

        Nothing to commit is not an error: the panel's button is enabled by the
        status it last saw, and a race with the agent writing a file must not
        show a failure.
        """
        message = (message or "").strip()
        if not message:
            raise VcsError("a commit needs a message")
        if "\x00" in message:
            raise VcsError("a commit message cannot contain a NUL byte")
        if not await self._is_repo():
            raise VcsError("this workspace is not a git repository")
        if not await self._files():
            return None
        args = ["commit", "-m", message]
        if not await self._has_identity():
            args = [*_FALLBACK_IDENTITY, *args]
        await self._run("add", "--all")
        await self._run(*args)
        _, sha = await self._run("rev-parse", "--short", "HEAD")
        return sha.strip()

    async def branch(self) -> str | None:
        if not await self._is_repo():
            return None
        # Unborn HEAD -- a repository with no commits -- has no branch name yet.
        code, out = await self._run("rev-parse", "--abbrev-ref", "HEAD", check=False)
        return out.strip() if code == 0 else None

    async def switch(self, name: str, *, create: bool = False) -> str:
        name = (name or "").strip()
        if not _BRANCH_RE.match(name) or ".." in name:
            raise VcsError(f"not a usable branch name: {name!r}")
        if not await self._is_repo():
            raise VcsError("this workspace is not a git repository")
        await self._run(*(("switch", "-c", name) if create else ("switch", name)))
        return name

    async def init(self) -> None:
        if await self._is_repo():
            return
        if not self._workspace.is_dir():
            raise VcsError("this session has no workspace to initialise")
        await self._run("init")
        # Only because *we* made this repository: a generated app vendors
        # node_modules and may hold a .env, and neither belongs in a history.
        # An existing repository keeps whatever ignore rules it already has.
        ignore = self._workspace / ".gitignore"
        if not ignore.exists():
            ignore.write_text(_INITIAL_GITIGNORE, encoding="utf-8")


def build_vcs(workspace: Path) -> Vcs:
    """The one place a workspace becomes a version-control provider."""
    return GitVcs(workspace)
