# tests/test_retention.py
"""R3-T7 (BE-11): deleted workspaces are recoverable, but not forever.

A session delete moves the workspace to <workspace_dir>/.trash/<sid>-<stamp>.
Nothing ever removed those, so every mistake stayed on disk (with its
node_modules) for good. The sweep is destructive-adjacent, so it is pinned
hard: only our own naming, only inside .trash, and retention 0 disables it.
"""

import logging
import os
import time
from pathlib import Path

import pytest

from vibe.approvals import ApprovalStore
from vibe.config import Settings
from vibe.events import EventLog
from vibe.lifecycle import SessionLifecycle
from vibe.models import ModelRef
from vibe.runs import RunRegistry
from vibe.store import SessionStore

# A name our own delete path produces: 12 lowercase hex chars, a dash, a UTC
# stamp YYYYMMDD-HHMMSS.
OURS = "a1b2c3d4e5f6-20260101-120000"


def _lifecycle(tmp_path, **overrides):
    store = overrides.get("store") or SessionStore(tmp_path / "sessions.db")
    return SessionLifecycle(
        store=store,
        event_log=overrides.get("event_log") or EventLog(tmp_path / "events.db"),
        executors={},
        autorun_policies={},
        approvals=ApprovalStore(),
        runs=RunRegistry(),
        workspace_dir=tmp_path,
        trash_retention_days=overrides.get("trash_retention_days", 14),
    )


def _trash_entry(tmp_path, name, age_days) -> Path:
    entry = tmp_path / ".trash" / name
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "package.json").write_text("{}", encoding="utf-8")
    stamp = time.time() - age_days * 86400
    os.utime(entry, (stamp, stamp))
    return entry


# --- what is reaped ---------------------------------------------------------


@pytest.mark.asyncio
async def test_an_old_entry_is_removed_and_logged_with_its_age(tmp_path, caplog):
    lc = _lifecycle(tmp_path)
    old = _trash_entry(tmp_path, OURS, age_days=20)
    with caplog.at_level(logging.INFO, logger="vibe.lifecycle"):
        removed = await lc.sweep_trash()
    assert removed == [old]
    assert not old.exists()
    messages = [r.getMessage() for r in caplog.records if old.name in r.getMessage()]
    assert messages, caplog.text
    assert "days old" in messages[0], "each removal is logged with the age that justified it"


@pytest.mark.asyncio
async def test_a_recent_entry_is_kept(tmp_path):
    lc = _lifecycle(tmp_path)
    recent = _trash_entry(tmp_path, OURS, age_days=1)
    assert await lc.sweep_trash() == []
    assert recent.exists(), "a mistaken delete stays recoverable for the window"


@pytest.mark.asyncio
async def test_retention_zero_disables_the_sweep_entirely(tmp_path):
    lc = _lifecycle(tmp_path, trash_retention_days=0)
    ancient = _trash_entry(tmp_path, OURS, age_days=365)
    assert await lc.sweep_trash() == []
    assert ancient.exists()


@pytest.mark.asyncio
async def test_a_missing_trash_directory_is_a_noop(tmp_path):
    assert await _lifecycle(tmp_path).sweep_trash() == []


# --- what must never be reaped ---------------------------------------------


@pytest.mark.asyncio
async def test_only_our_own_timestamped_names_are_removed(tmp_path):
    lc = _lifecycle(tmp_path)
    strangers = [
        "not-a-session",  # no stamp at all
        "a1b2c3d4e5f6",  # session id, no stamp
        "A1B2C3D4E5F6-20260101-120000",  # ids are lowercase hex
        "a1b2c3d4e5f6-2026-01-01-120000",  # a stamp we never write
        "a1b2c3d4e5f6-20260101-120000-backup",  # our name plus a suffix
    ]
    for name in strangers:
        _trash_entry(tmp_path, name, age_days=90)
    # A file (not a directory) that happens to match must also be left alone.
    stray_file = tmp_path / ".trash" / "ffffffffffff-20260101-120000"
    stray_file.write_text("keep me", encoding="utf-8")
    stamp = time.time() - 90 * 86400
    os.utime(stray_file, (stamp, stamp))

    assert await lc.sweep_trash() == []
    for name in [*strangers, stray_file.name]:
        assert (tmp_path / ".trash" / name).exists(), name


@pytest.mark.asyncio
async def test_a_workspace_outside_trash_is_never_touched(tmp_path):
    lc = _lifecycle(tmp_path)
    outside = tmp_path / OURS  # a live session workspace
    outside.mkdir()
    stamp = time.time() - 90 * 86400
    os.utime(outside, (stamp, stamp))
    other = tmp_path / "user-notes"
    other.mkdir()
    os.utime(other, (stamp, stamp))

    assert await lc.sweep_trash() == []
    assert outside.exists() and other.exists()


# --- through the real delete path ------------------------------------------


@pytest.mark.asyncio
async def test_delete_reaps_old_trash_and_keeps_the_new_entry(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    lc = _lifecycle(tmp_path, store=store)
    old = _trash_entry(tmp_path, OURS, age_days=30)

    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    (tmp_path / sid).mkdir()

    await lc.delete(sid)

    assert not old.exists(), "the delete path is where trash grows, so it is where it is bounded"
    fresh = list((tmp_path / ".trash").iterdir())
    assert len(fresh) == 1 and fresh[0].name.startswith(sid)


# --- the setting ------------------------------------------------------------


def test_retention_defaults_to_fourteen_days(tmp_path):
    assert Settings(workspace_dir=tmp_path / "ws").trash_retention_days == 14


def test_retention_is_configurable_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("VIBE_WORKSPACE_DIR", str(tmp_path / "ws"))
    monkeypatch.setenv("VIBE_TRASH_RETENTION_DAYS", "3")
    assert Settings.from_env().trash_retention_days == 3
