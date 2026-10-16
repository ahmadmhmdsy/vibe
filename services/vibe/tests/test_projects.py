# tests/test_projects.py
"""M8/C1: where a session's workspace comes from.

Each provider gets its own test, and the two that write to disk are exercised
against a real filesystem in a tmp dir -- a folder import that only worked on an
empty directory, or a clone that only worked on a repository git could already
reach, would be the failure these are here to catch.

The route tests are the ones that matter for the seam being real: import is
reachable from a client, the path survives a restart, and deleting the session
leaves the user's own folder exactly where it was.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from vibe.models import ModelRef
from vibe.projects import (
    RULES_FILENAME,
    EmptyWorkspaceSource,
    GitRepoSource,
    LocalFolderSource,
    ProjectError,
    ViteReactTsTemplate,
    build_source,
    detect_project,
    project_briefing,
    read_rules,
)

_MODEL = {"provider_id": "openai", "model_id": "gpt-4o"}


def _vite_package_manifest() -> str:
    return json.dumps(
        {
            "dependencies": {"react": "^19.0.0", "react-dom": "^19.0.0"},
            "devDependencies": {"vite": "^6.0.0", "typescript": "^5.6.0"},
            "scripts": {"dev": "vite", "build": "tsc && vite build"},
        }
    )


# --- the default ----------------------------------------------------------


def test_the_empty_source_makes_the_directory_and_is_managed(tmp_path):
    layout = EmptyWorkspaceSource().materialize(tmp_path / "ws")
    assert layout.path == tmp_path / "ws"
    assert layout.path.is_dir()
    assert layout.managed is True


def test_detecting_a_project_with_no_manifest_is_not_an_error(tmp_path):
    """A folder of documents is still a folder the agent can work in."""
    info = detect_project(tmp_path)
    assert info.stack == "unknown"
    assert info.start_command is None


def test_detection_reports_a_vite_react_project_as_runnable(tmp_path):
    (tmp_path / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    info = detect_project(tmp_path)
    assert info.stack == "vite-react-ts"
    assert info.framework == "React + Vite"
    assert info.start_command == "pnpm dev"
    assert info.language == "TypeScript"


def test_an_unreadable_manifest_is_treated_as_no_manifest(tmp_path):
    """A half-written package.json must not turn a file listing into a 500."""
    (tmp_path / "package.json").write_text("{ not json", encoding="utf-8")
    assert detect_project(tmp_path).stack == "unknown"


# --- the template ---------------------------------------------------------


def test_the_template_writes_a_runnable_app(tmp_path):
    source = ViteReactTsTemplate()
    layout = source.materialize(tmp_path / "app")

    assert layout.managed is True
    assert (tmp_path / "app" / "package.json").is_file()
    assert (tmp_path / "app" / "index.html").is_file()
    assert (tmp_path / "app" / "src" / "App.tsx").is_file()
    # package.json and index.html are the two files the executor needs: one for
    # `pnpm install`, one for vite's entry point.
    assert json.loads((tmp_path / "app" / "package.json").read_text())["scripts"]["dev"] == "vite"
    assert "/src/main.tsx" in (tmp_path / "app" / "index.html").read_text()


def test_the_scaffold_describes_itself_and_does_not_clobber_edits(tmp_path):
    source = ViteReactTsTemplate()
    source.materialize(tmp_path / "app")
    info = source.describe()
    assert info.stack == "vite-react-ts"
    assert info.language == "TypeScript"

    edited = tmp_path / "app" / "src" / "App.tsx"
    edited.write_text("export default function App() { return <p>mine</p> }", encoding="utf-8")
    source.materialize(tmp_path / "app")
    assert "mine" in edited.read_text()


# --- a local folder, in place ---------------------------------------------


def test_a_folder_import_is_in_place_and_unmanaged(tmp_path):
    folder = tmp_path / "my-app"
    folder.mkdir()
    (folder / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")

    layout = LocalFolderSource(folder).materialize(tmp_path / "would-be-dest")

    assert layout.path == folder.resolve()
    # Unmanaged is what stops the lifecycle moving the user's own directory aside
    # when the session is deleted.
    assert layout.managed is False
    assert not (tmp_path / "would-be-dest").exists()


def test_a_folder_import_describes_the_folder_it_was_pointed_at(tmp_path):
    folder = tmp_path / "my-app"
    folder.mkdir()
    (folder / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    assert LocalFolderSource(folder).describe().stack == "vite-react-ts"


def test_a_folder_that_is_not_there_is_a_project_error(tmp_path):
    with pytest.raises(ProjectError, match="not a folder"):
        LocalFolderSource(tmp_path / "missing").materialize(tmp_path / "dest")


def test_a_folder_import_expands_a_home_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "code").mkdir()
    layout = LocalFolderSource("~/code").materialize(tmp_path / "dest")
    assert layout.path == (tmp_path / "code").resolve()


# --- a git repository ------------------------------------------------------


def _git_origin(tmp_path: Path) -> Path:
    """A real repository with one commit, to clone from."""
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=origin, check=True)
    subprocess.run(["git", "add", "."], cwd=origin, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=origin, check=True, env=env)
    return origin


def test_a_git_import_clones_the_repository_into_the_destination(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    origin = _git_origin(tmp_path)
    source = GitRepoSource(str(origin))

    layout = source.materialize(tmp_path / "clone")

    assert layout.path == tmp_path / "clone"
    assert layout.managed is True
    assert (tmp_path / "clone" / "package.json").is_file()
    assert source.describe().stack == "vite-react-ts"


def test_a_repository_git_cannot_reach_is_a_project_error(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    with pytest.raises(ProjectError):
        GitRepoSource(str(tmp_path / "no-such-repo")).materialize(tmp_path / "clone")


def test_a_git_import_refuses_a_destination_that_already_has_files(tmp_path):
    dest = tmp_path / "clone"
    dest.mkdir()
    (dest / "keep.txt").write_text("x")
    with pytest.raises(ProjectError, match="already has files"):
        GitRepoSource("https://example.invalid/x").materialize(dest)


# --- the name-to-provider mapping -----------------------------------------


def test_build_source_names_a_provider_or_refuses(tmp_path):
    assert build_source("empty").name == "empty"
    assert build_source("template").name == "template"
    assert build_source("folder", path=str(tmp_path)).name == "folder"
    assert build_source("git", url="https://example.invalid/x").name == "git"
    with pytest.raises(ProjectError, match="needs a path"):
        build_source("folder")
    with pytest.raises(ProjectError, match="needs a url"):
        build_source("git")
    with pytest.raises(ProjectError, match="unknown project source"):
        build_source("dropbox")


# --- describe() reaching the model ----------------------------------------


def test_the_briefing_says_nothing_about_an_empty_workspace(tmp_path):
    # The built-in prompt already describes the app to build; a second copy here
    # would be two sources of truth for the same sentence.
    assert project_briefing(tmp_path) == ""


def test_the_briefing_says_nothing_about_a_workspace_it_cannot_recognise(tmp_path):
    (tmp_path / "notes.txt").write_text("some documents")
    assert project_briefing(tmp_path) == ""


def test_the_briefing_describes_an_imported_app(tmp_path):
    (tmp_path / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    briefing = project_briefing(tmp_path)
    assert "React + Vite" in briefing
    assert "TypeScript" in briefing
    assert "pnpm dev" in briefing


def test_the_briefing_carries_the_projects_own_rules(tmp_path):
    (tmp_path / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    (tmp_path / RULES_FILENAME).write_text("Never use a class component.")
    assert "Never use a class component." in project_briefing(tmp_path)


def test_the_rules_file_is_read_even_without_a_recognisable_stack(tmp_path):
    """The user's own file is an explicit statement about a project, so it is
    honoured wherever it is, whatever the detection made of the folder."""
    (tmp_path / RULES_FILENAME).write_text("This is a Rust service. Do not add npm.")
    assert "This is a Rust service" in project_briefing(tmp_path)


def test_a_rules_directory_or_an_empty_rules_file_reads_as_absent(tmp_path):
    (tmp_path / RULES_FILENAME).mkdir()
    assert read_rules(tmp_path) is None
    (tmp_path / RULES_FILENAME).rmdir()
    (tmp_path / RULES_FILENAME).write_text("   \n")
    assert read_rules(tmp_path) is None


def test_the_project_paragraph_is_appended_to_the_prompt_but_an_override_still_wins(tmp_path):
    from vibe.prompts import DEFAULT_SYSTEM_PROMPT, system_prompt_for

    (tmp_path / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    briefing = project_briefing(tmp_path)

    default = system_prompt_for(None, project=briefing)
    assert default.startswith(DEFAULT_SYSTEM_PROMPT)
    assert default.endswith(briefing)

    overridden = system_prompt_for("be terse", project=briefing)
    assert overridden.startswith("be terse")
    assert overridden != "be terse"  # the project paragraph is still added

    # No project context leaves the prompt exactly as it was before imports.
    assert system_prompt_for(None) == DEFAULT_SYSTEM_PROMPT
    assert system_prompt_for("  be terse  ") == "be terse"


def test_the_composer_context_for_an_imported_project_names_its_stack(client, app, tmp_path):
    """The seam is only real if describe() reaches the model, not just the route."""
    from conftest import swap

    folder = _existing_app(tmp_path)
    sid = _import_folder(client, folder)["id"]

    systems: list = []

    class _Recording:
        async def run(self, input, ctx):
            systems.append(input.system)
            from vibe.models import AgentEvent

            yield AgentEvent(kind="text_chunk", data={"text": "ok"})
            yield AgentEvent(kind="turn_complete", data={})

    swap(app, runtime=_Recording())
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "what is this?"})
    assert resp.status_code == 200, resp.text

    assert systems and "React + Vite" in systems[0]
    assert "not an empty directory" in systems[0]


# --- through the API -------------------------------------------------------


def test_creating_a_session_without_a_source_leaves_the_workspace_empty(client, container, session_id):
    """Every client that predates sources keeps the behaviour it had."""
    assert client.get(f"/sessions/{session_id}/files").json() == []
    assert client.post("/sessions", json={"model": _MODEL}).json()["project"]["stack"] == "empty"
    assert container.session_service.workspace_path(session_id) == container.settings.workspace_dir / session_id


def test_creating_a_session_from_the_template_reports_and_scaffolds(client):
    sid = client.post("/sessions", json={"model": _MODEL, "source": {"kind": "template"}}).json()["id"]

    assert client.get(f"/sessions/{sid}/files").json() == [
        ".gitignore",
        "AI_RULES.md",
        "index.html",
        "package.json",
        "src/App.tsx",
        "src/main.tsx",
        "tsconfig.json",
        "vite.config.ts",
    ]


def _import_folder(client, folder: Path) -> dict:
    resp = client.post("/sessions", json={"model": _MODEL, "source": {"kind": "folder", "path": str(folder)}})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _existing_app(tmp_path: Path) -> Path:
    folder = tmp_path / "existing"
    (folder / "src").mkdir(parents=True)
    (folder / "src" / "App.tsx").write_text("export default () => null")
    (folder / "package.json").write_text(_vite_package_manifest(), encoding="utf-8")
    return folder


def test_importing_a_folder_makes_the_session_work_in_it(client, tmp_path):
    folder = _existing_app(tmp_path)
    body = _import_folder(client, folder)
    sid = body["id"]

    assert body["project"]["stack"] == "vite-react-ts"
    assert body["project"]["start_command"] == "pnpm dev"
    # The session reads and writes the folder the user pointed at.
    assert client.get(f"/sessions/{sid}/files").json() == ["package.json", "src/App.tsx"]
    assert client.get(f"/sessions/{sid}/files/src/App.tsx").json()["content"] == "export default () => null"


async def test_the_imported_path_is_on_the_row_so_a_restart_still_finds_it(client, container, tmp_path):
    sid = _import_folder(client, _existing_app(tmp_path))["id"]

    # Read from the store, the way a restarted process would: the path is not
    # derivable from the session id, so it has to be written down.
    row = await container.store.get_session(sid)
    assert row is not None and row.workspace_path == str((tmp_path / "existing").resolve())


def test_deleting_an_imported_session_leaves_the_users_folder_alone(client, app, tmp_path):
    folder = tmp_path / "existing"
    folder.mkdir()
    (folder / "notes.txt").write_text("important")
    sid = client.post("/sessions", json={"model": _MODEL, "source": {"kind": "folder", "path": str(folder)}}).json()[
        "id"
    ]

    assert client.delete(f"/sessions/{sid}").status_code == 204

    assert (folder / "notes.txt").read_text() == "important"
    trash = app.state.container.settings.workspace_dir / ".trash"
    assert not trash.exists() or list(trash.iterdir()) == []


def test_a_refused_source_is_a_400_and_leaves_no_session_behind(client, tmp_path):
    resp = client.post(
        "/sessions", json={"model": _MODEL, "source": {"kind": "folder", "path": str(tmp_path / "nope")}}
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_failed"
    assert client.get("/sessions").json() == []


def test_an_unknown_source_kind_is_rejected_by_the_schema(client):
    resp = client.post("/sessions", json={"model": _MODEL, "source": {"kind": "dropbox"}})
    assert resp.status_code == 400


def _sync(awaitable):
    """Run a store coroutine from a sync test."""
    import asyncio

    return asyncio.run(awaitable)


def test_the_service_caches_the_imported_path_after_create(tmp_path):
    """`workspace_path` is sync and called on the file hot path, so `create` has
    to leave the answer in memory rather than making every read hit the store."""
    from vibe.services.sessions import SessionService

    class _Lifecycle:
        async def delete(self, sid, owner_id=None): ...

    class _Store:
        async def create_session(self, model_ref, owner_id):
            return "s1"

        async def set_workspace_path(self, sid, path, owner_id): ...  # pragma: no cover

        async def delete_session(self, sid, owner_id): ...  # pragma: no cover

    folder = tmp_path / "existing"
    folder.mkdir()
    svc = SessionService(store=_Store(), lifecycle=_Lifecycle(), workspace_dir=tmp_path / "ws")

    import asyncio

    sid = asyncio.run(svc.create(ModelRef("openai", "gpt-4o"), "local", source=LocalFolderSource(folder)))

    assert svc.workspace_path(sid) == folder.resolve()
