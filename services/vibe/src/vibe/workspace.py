# services/vibe/src/vibe/workspace.py
"""Workspace file enumeration shared by the API and the agent's file tools.

A generated project vendors its dependencies into the workspace, so an
unfiltered walk reports thousands of paths nobody asked for (one session
returned 3680 paths, 3667 of them under node_modules) and pays that cost on
every chat turn, twice, for the changed-file snapshot.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

IGNORED_DIRS = frozenset({
    "node_modules",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    ".parcel-cache",
    "coverage",
    "htmlcov",
    ".cache",
    # Workspaces of deleted sessions are moved here rather than removed, so a
    # delete stays recoverable. It must not appear in a file listing.
    ".trash",
    ".idea",
    ".vscode",
})


def is_ignored(relpath: str | Path) -> bool:
    return any(part in IGNORED_DIRS for part in Path(relpath).parts)


def iter_workspace_files(root: Path, limit: int | None = None) -> Iterator[Path]:
    """Yield files under root, pruning ignored directories from the walk.

    Pruning during the walk (rather than filtering afterwards) keeps a vendored
    tree from being descended at all. Order is walk order; callers that need a
    stable order sort the result.
    """
    if not root.exists():
        return
    emitted = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def relative_files(root: Path, limit: int | None = None) -> list[str]:
    """Workspace-relative POSIX paths, sorted."""
    return sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in iter_workspace_files(root, limit=limit)
    )
