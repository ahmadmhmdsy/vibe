"""Merge the workspace roots that an un-expanded `~` scattered across the repo.

Background: `VIBE_WORKSPACE_DIR=~/vibe-workspaces` was taken literally, so every
directory the server was launched from grew its own root — `./~/vibe-workspaces`,
`services/vibe/~/vibe-workspaces` — alongside the correct `Path.home()` one. Each
has its own `sessions.db`, so the sessions in one root are invisible from another.

This copies every session directory into the target root and merges the
`sessions` tables, so nothing is lost. **Originals are never modified or
deleted** — verify the result, then remove them yourself.

    python scripts/merge_workspaces.py            # report only (default)
    python scripts/merge_workspaces.py --apply    # copy + merge
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET = Path.home() / "vibe-workspaces"

# Every root the literal-`~` bug could have produced, most authoritative first.
# The services/vibe one holds the real sessions.db and providers.json.
SOURCES = [
    REPO_ROOT / "services" / "vibe" / "~" / "vibe-workspaces",
    REPO_ROOT / "~" / "vibe-workspaces",
]


def _session_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name != ".trash")


def _count_rows(db: Path) -> int:
    if not db.is_file():
        return 0
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0


def _copy_missing(src: Path, dst: Path) -> int:
    """Copy files that do not exist at the destination. Never overwrites."""
    copied = 0
    # Create the destination itself: an empty source session dir yields no rglob
    # entries, so without this its (empty) directory would be silently dropped
    # and the session would have no workspace at all.
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        out = dst / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, out)
        copied += 1
    return copied


def _merge_sessions_db(target_db: Path, source_db: Path) -> int:
    """INSERT OR IGNORE every row of source_db.sessions into target_db."""
    if not source_db.is_file():
        return 0
    before = _count_rows(target_db)
    con = sqlite3.connect(target_db)
    try:
        con.execute("ATTACH DATABASE ? AS src", (str(source_db),))
        con.execute(
            "INSERT OR IGNORE INTO sessions (id, title, model_ref, created_at, updated_at) "
            "SELECT id, title, model_ref, created_at, updated_at FROM src.sessions"
        )
        con.commit()
        con.execute("DETACH DATABASE src")
    finally:
        con.close()
    return _count_rows(target_db) - before


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually copy and merge")
    args = ap.parse_args()

    print(f"repo root : {REPO_ROOT}")
    print(f"target    : {TARGET}")
    print(f"mode      : {'APPLY' if args.apply else 'DRY RUN (pass --apply to write)'}\n")

    present = [s for s in SOURCES if s.is_dir()]
    if not present:
        print("No literal-~ workspace roots found — nothing to migrate.")
        return 0

    total_dirs = 0
    for src in present:
        dirs = _session_dirs(src)
        total_dirs += len(dirs)
        print(f"source    : {src}")
        print(f"            {len(dirs)} session dirs, "
              f"{_count_rows(src / 'sessions.db')} session rows, "
              f"providers.json={'yes' if (src / 'providers.json').is_file() else 'no'}")

    existing = _session_dirs(TARGET)
    print(f"\ntarget already has {len(existing)} session dirs, "
          f"{_count_rows(TARGET / 'sessions.db')} session rows")

    if not args.apply:
        print("\nNothing written. Re-run with --apply.")
        return 0

    TARGET.mkdir(parents=True, exist_ok=True)

    # Back up the target's own index before merging anything into it.
    target_db = TARGET / "sessions.db"
    if target_db.is_file():
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = target_db.with_suffix(f".db.bak-{stamp}")
        shutil.copy2(target_db, backup)
        print(f"\nbacked up target index -> {backup.name}")

    # The authoritative source seeds the target index if there is not one yet.
    if not target_db.is_file():
        richest = max(present, key=lambda s: _count_rows(s / "sessions.db"))
        if (richest / "sessions.db").is_file():
            shutil.copy2(richest / "sessions.db", target_db)
            print(f"seeded target index from {richest}")

    copied_files = 0
    for src in present:
        for d in _session_dirs(src):
            copied_files += _copy_missing(d, TARGET / d.name)

    added = 0
    for src in present:
        added += _merge_sessions_db(target_db, src / "sessions.db")

    # providers.json only ever existed in the services/vibe root.
    provider_note = "target already had one"
    if not (TARGET / "providers.json").is_file():
        for src in present:
            if (src / "providers.json").is_file():
                shutil.copy2(src / "providers.json", TARGET / "providers.json")
                provider_note = f"copied from {src}"
                break
        else:
            provider_note = "none found in any source"

    print(f"\ncopied {copied_files} missing files")
    print(f"merged {added} new session rows")
    print(f"providers.json: {provider_note}")
    print(f"\nRESULT: {len(_session_dirs(TARGET))} session dirs, "
          f"{_count_rows(target_db)} session rows in {TARGET}")
    print("Originals left untouched — verify, then delete them yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
