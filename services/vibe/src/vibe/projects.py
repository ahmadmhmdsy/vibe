# services/vibe/src/vibe/projects.py
"""Where a session's workspace comes from (M8 / C1).

`ensure_workspace` used to be the whole story: every session got an empty
directory named after its id, and the agent had to invent a package.json before
anything would run. That is one way to start, and it is the wrong one for the
second audience -- someone who already has an app on disk.

A `ProjectSource` is the seam between "the user asked for a session" and "there
is a project in the workspace":

* ``materialize(dest)`` puts a project at the destination the service offers and
  says where it actually landed. An in-place import returns a path that is not
  the destination, which is a normal outcome rather than a special case.
* ``describe()`` says what the project *is*, so the stack stops being a
  hard-coded "React + Vite" wherever it is mentioned.

Adding a stack, or a new way to bring code in, is a new provider here and
nothing else: `SessionService.create` names a source and never a kind.

Two invariants every provider keeps:

* ``materialize`` writes only inside ``dest`` -- except `LocalFolderSource`,
  whose entire purpose is a directory that already exists.
* ``managed`` is what the session lifecycle may move aside when the session is
  deleted. An imported folder is the user's own directory, so deleting the
  session must leave it exactly where it was.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProjectError(ValueError):
    """The request cannot be turned into a project.

    A ValueError subclass so a route's existing "bad input -> 400" handling
    covers it: a missing folder or an unreachable repository is the caller's
    mistake, not a crash.
    """


@dataclass(frozen=True)
class ProjectLayout:
    """Where the project ended up, and whether the app owns that directory."""

    path: Path
    managed: bool


@dataclass(frozen=True)
class ProjectInfo:
    """What the project is.

    Deliberately shallow. The executor needs to know whether there is a web app
    to install and run, and the composer wants to say what it is looking at;
    neither needs a framework classifier.
    """

    stack: str
    framework: str
    start_command: str | None = None
    language: str | None = None


class ProjectSource(Protocol):
    """Puts a project in the session's workspace."""

    name: str

    def materialize(self, dest: Path) -> ProjectLayout: ...

    def describe(self) -> ProjectInfo: ...


#: A Vite + React + TypeScript app, pinned to the versions this repository's own
#: frontend uses. Written as files rather than shelling out to
#: `pnpm create vite`, so scaffolding needs no network, cannot pick up a
#: different template version than the one reviewed here, and cannot fail
#: halfway through a download.
_TEMPLATE_FILES: dict[str, str] = {
    "package.json": """\
{
  "name": "vibe-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
""",
    "index.html": """\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>vibe app</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
    "vite.config.ts": """\
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
});
""",
    "tsconfig.json": """\
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
""",
    ".gitignore": """\
node_modules
dist
.env
.env.*
*.local
.DS_Store
""",
    "AI_RULES.md": """\
# AI_RULES.md

Instructions for the coding agent working in this project. Edit freely: this
file is read on every turn and is the project's own half of the agent's standing
instructions (the operator's half lives in the app's Settings).

- This is a React 19 + Vite project written in TypeScript.
- Run it with `pnpm dev`; it must build with `pnpm build` after every change.
""",
    "src/main.tsx": """\
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
""",
    "src/App.tsx": """\
export default function App() {
  return (
    <main style={{ fontFamily: "system-ui", padding: 32 }}>
      <h1>vibe app</h1>
      <p>This project is ready. Ask the agent to build something.</p>
    </main>
  );
}
""",
}


#: The file a project can carry its own agent instructions in. Read on every
#: turn, so an edit takes effect on the next message rather than the next
#: restart; the operator's half of the prompt lives in the app's Settings.
RULES_FILENAME = "AI_RULES.md"

#: Stacks the agent can install and run. Detection returns one of these for a
#: real app, and "unknown" for anything else -- which is also what an empty
#: directory looks like, so the briefing only speaks up for these.
_RUNNABLE_STACKS = frozenset({"vite-react-ts", "node"})


def detect_project(path: Path) -> ProjectInfo:
    """Read what kind of project sits at ``path`` from the files that are there.

    package.json is the only file consulted, because it is the only one the
    executor cares about: it runs ``pnpm install`` and then ``pnpm run dev``, so
    the question being answered is "is there a runnable web app here", not
    "which framework is this". An unreadable or absent manifest is not an error
    -- a folder of documents is a project the agent can still work in.
    """
    manifest = path / "package.json"
    data: dict = {}
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            data = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            data = {}
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    scripts = data.get("scripts") or {}
    has_dev = isinstance(scripts, dict) and "dev" in scripts
    language = "TypeScript" if "typescript" in deps else "JavaScript" if deps else None
    if "react" in deps and "vite" in deps:
        return ProjectInfo(
            stack="vite-react-ts",
            framework="React + Vite",
            start_command="pnpm dev" if has_dev else None,
            language=language,
        )
    if has_dev:
        return ProjectInfo(stack="node", framework="Node", start_command="pnpm dev", language=language)
    return ProjectInfo(stack="unknown", framework="Plain files")


def read_rules(workspace: Path) -> str | None:
    """The project's own instructions, if it carries any.

    A folder, a broken symlink or a file that cannot be decoded is the same
    answer as no file at all: a project without rules is normal, and nothing
    about reading them may fail a turn.
    """
    try:
        text = (workspace / RULES_FILENAME).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text or None


def project_briefing(workspace: Path) -> str:
    """What the agent should be told about the project it is working in.

    This is `describe()` reaching the model: the composer's context used to be a
    hard-coded "React 19 with TypeScript and Vite" in the system prompt, which is
    a lie in an imported folder and a duplicate of the built-in prompt in an
    empty one. So an unrecognised or empty workspace produces nothing at all --
    the built-in prompt already says what to build -- and a real project produces
    one paragraph about what is actually there, followed by the project's own
    rules file when it has one.
    """
    parts: list[str] = []
    info = detect_project(workspace)
    if info.stack in _RUNNABLE_STACKS:
        what = f"The workspace holds an existing {info.framework} project"
        if info.language:
            what += f" written in {info.language}"
        what += ", not an empty directory. Read what is there and match its conventions."
        if info.start_command:
            what += f" It is started with `{info.start_command}`."
        parts.append(what)
    rules = read_rules(workspace)
    if rules:
        parts.append(f"The project's own instructions ({RULES_FILENAME}):\n\n{rules}")
    return "\n\n".join(parts)


class EmptyWorkspaceSource:
    """The default: an empty directory the agent fills in.

    This is what every session had before this module existed, so it stays the
    default and no existing client's behaviour changes -- a client that does not
    know about sources still gets exactly the workspace it used to.
    """

    name = "empty"

    def materialize(self, dest: Path) -> ProjectLayout:
        dest.mkdir(parents=True, exist_ok=True)
        return ProjectLayout(path=dest, managed=True)

    def describe(self) -> ProjectInfo:
        return ProjectInfo(stack="empty", framework="Empty workspace")


class ViteReactTsTemplate:
    """Scaffold a runnable React + Vite + TypeScript app."""

    name = "template"

    def __init__(self) -> None:
        self._dest: Path | None = None

    def materialize(self, dest: Path) -> ProjectLayout:
        for relpath, content in _TEMPLATE_FILES.items():
            target = dest / relpath
            if target.exists():
                # Never clobber a file the agent or the user already wrote: a
                # scaffold is a starting point, and re-running it must be safe.
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self._dest = dest
        return ProjectLayout(path=dest, managed=True)

    def describe(self) -> ProjectInfo:
        if self._dest is None:
            raise ProjectError("describe() before materialize()")
        return detect_project(self._dest)


class LocalFolderSource:
    """Work in a folder the user already has, in place.

    In-place is the point: copying someone's repository into a hidden workspace
    would mean two copies drifting apart, and edits they make in their own
    editor would be invisible here. The folder is therefore unmanaged -- the
    session lifecycle must never move or delete it.
    """

    name = "folder"

    def __init__(self, folder: str | Path) -> None:
        # expanduser, so "~/code/app" typed into the UI means what the user means.
        self._folder = Path(folder).expanduser()

    def materialize(self, dest: Path) -> ProjectLayout:
        folder = self._folder.resolve()
        if not folder.is_dir():
            raise ProjectError(f"not a folder: {self._folder}")
        return ProjectLayout(path=folder, managed=False)

    def describe(self) -> ProjectInfo:
        return detect_project(self._folder)


class GitRepoSource:
    """Clone a repository into the session workspace.

    Managed, because the app made the clone: it created the directory, so it may
    remove it, and the repository itself is still wherever the user cloned it
    from. Nothing is pushed -- a remote is a user action, never a side effect.
    """

    name = "git"

    def __init__(self, url: str) -> None:
        self._url = url
        self._dest: Path | None = None

    def materialize(self, dest: Path) -> ProjectLayout:
        if not self._url.strip():
            raise ProjectError("a git import needs a repository URL")
        if dest.exists() and any(dest.iterdir()):
            raise ProjectError(f"{dest.name} already has files in it")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", self._url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise ProjectError("git is not installed or not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            # git's own last line says what went wrong ("repository not found",
            # "could not resolve host"), which is more use than an exit code.
            detail = (exc.stderr or "").strip().splitlines()
            raise ProjectError(detail[-1] if detail else f"git clone failed ({exc.returncode})") from exc
        self._dest = dest
        return ProjectLayout(path=dest, managed=True)

    def describe(self) -> ProjectInfo:
        if self._dest is None:
            raise ProjectError("describe() before materialize()")
        return detect_project(self._dest)


def build_source(kind: str, *, path: str | None = None, url: str | None = None) -> ProjectSource:
    """The one place a requested kind becomes a provider.

    A route hands over what the client asked for; the mapping from name to
    provider lives here, next to the providers themselves.
    """
    if kind == EmptyWorkspaceSource.name:
        return EmptyWorkspaceSource()
    if kind == ViteReactTsTemplate.name:
        return ViteReactTsTemplate()
    if kind == LocalFolderSource.name:
        if not path:
            raise ProjectError("a folder import needs a path")
        return LocalFolderSource(path)
    if kind == GitRepoSource.name:
        if not url:
            raise ProjectError("a git import needs a url")
        return GitRepoSource(url)
    raise ProjectError(f"unknown project source: {kind!r}")


def remove_workspace(path: Path) -> None:
    """Best-effort cleanup for a workspace a failed materialize left behind.

    Only ever called on a destination this app created (``<workspace>/<sid>``),
    so it cannot touch an imported folder.
    """
    shutil.rmtree(path, ignore_errors=True)
