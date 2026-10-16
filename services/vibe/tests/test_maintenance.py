"""Tests for vibe.maintenance (R5-T7).

Every test runs against tmp_path. The commands under test must never touch the
user's real workspace, and nothing here reads VIBE_WORKSPACE_DIR.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from vibe import events as events_module
from vibe import store as store_module
from vibe.maintenance import (
    BACKUPS_DIRNAME,
    MANIFEST_NAME,
    backup,
    backup_exit_code,
    render_backup,
    render_repair,
    repair,
    repair_exit_code,
)


def _db(path: Path, title: str = "first") -> sqlite3.Connection:
    """A sessions.db with one committed row, in WAL mode."""
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    connection.execute("INSERT INTO sessions (id, title) VALUES (?, ?)", ("s1", title))
    connection.commit()
    return connection


def _backups(workspace: Path) -> list[Path]:
    return sorted(path for path in (workspace / BACKUPS_DIRNAME).iterdir() if path.is_dir())


def test_backup_saves_both_databases_and_the_provider_file(tmp_path: Path) -> None:
    _db(tmp_path / "sessions.db").close()
    _db(tmp_path / "events.db").close()
    (tmp_path / "providers.json").write_text('{"p1": {"id": "p1"}}', encoding="utf-8")

    result = backup(tmp_path)

    assert result.ok, result.errors
    assert set(result.files) == {"sessions.db", "events.db", "providers.json"}
    assert result.size_bytes > 0
    assert (result.directory / MANIFEST_NAME).exists()
    assert result.directory.parent == tmp_path / BACKUPS_DIRNAME


def test_backup_snapshot_is_a_database_a_fresh_workspace_can_read(tmp_path: Path) -> None:
    _db(tmp_path / "sessions.db", "restore me").close()

    result = backup(tmp_path)

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "sessions.db").write_bytes((result.directory / "sessions.db").read_bytes())
    connection = sqlite3.connect(fresh / "sessions.db")
    try:
        assert connection.execute("SELECT title FROM sessions").fetchone()[0] == "restore me"
    finally:
        connection.close()


def test_backup_of_a_live_wal_database_keeps_the_row_and_no_sidecars(tmp_path: Path) -> None:
    """The source stays open (its data still lives in the -wal file) while we copy."""
    live = _db(tmp_path / "sessions.db", "in the wal")
    try:
        assert (tmp_path / "sessions.db-wal").exists()

        result = backup(tmp_path)

        assert result.ok, result.errors
        assert not (result.directory / "sessions.db-wal").exists()
        assert not (result.directory / "sessions.db-shm").exists()
        connection = sqlite3.connect(result.directory / "sessions.db")
        try:
            assert connection.execute("SELECT title FROM sessions").fetchone()[0] == "in the wal"
        finally:
            connection.close()
    finally:
        live.close()


def test_backup_prunes_old_backups_and_keeps_the_newest(tmp_path: Path) -> None:
    root = tmp_path / BACKUPS_DIRNAME
    for stamp in ("20200101-000000", "20200101-000001", "20200101-000002"):
        (root / stamp).mkdir(parents=True)

    result = backup(tmp_path, keep=3)

    names = [path.name for path in _backups(tmp_path)]
    # Three old ones plus the new one is four; keeping three drops exactly the
    # oldest by name, not the oldest by insertion order.
    assert "20200101-000000" not in names
    assert "20200101-000001" in names
    assert "20200101-000002" in names
    assert result.directory.name in names
    assert len(names) == 3
    assert [path.name for path in result.removed] == ["20200101-000000"]


def test_backup_never_prunes_a_directory_it_did_not_create(tmp_path: Path) -> None:
    """A stray folder under backups/ is the user's; pruning it would lose data."""
    kept = tmp_path / BACKUPS_DIRNAME / "notes-from-me"
    kept.mkdir(parents=True)
    (kept / "keep.txt").write_text("do not delete", encoding="utf-8")

    backup(tmp_path, keep=1)

    assert (kept / "keep.txt").read_text(encoding="utf-8") == "do not delete"


def test_backup_reports_missing_files_without_failing(tmp_path: Path) -> None:
    result = backup(tmp_path)

    assert result.ok
    assert result.files == {}
    assert sorted(result.missing) == ["events.db", "providers.json", "sessions.db"]
    assert backup_exit_code(result) == 0
    assert "not present" in render_backup(result)


def test_backup_fails_loudly_on_a_corrupt_database(tmp_path: Path) -> None:
    (tmp_path / "sessions.db").write_bytes(b"this is not a database" * 64)
    (tmp_path / "providers.json").write_text("{}", encoding="utf-8")

    result = backup(tmp_path)

    assert not result.ok
    assert backup_exit_code(result) == 1
    assert len(result.errors) == 1 and "sessions.db" in result.errors[0]
    assert result.files == {"providers.json": 2}
    assert "INCOMPLETE" in render_backup(result)
    assert (tmp_path / "sessions.db").exists()


def test_backup_refuses_to_keep_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        backup(tmp_path, keep=0)


def test_backup_leaves_the_original_database_and_generated_projects_alone(tmp_path: Path) -> None:
    _db(tmp_path / "sessions.db").close()
    original = (tmp_path / "sessions.db").read_bytes()
    project = tmp_path / "projects" / "abc123" / "src"
    project.mkdir(parents=True)
    (project / "App.tsx").write_text("export default 1", encoding="utf-8")

    result = backup(tmp_path)

    assert (tmp_path / "sessions.db").read_bytes() == original
    assert (project / "App.tsx").exists()
    assert not (result.directory / "projects").exists()


def test_repair_migrates_an_empty_workspace(tmp_path: Path) -> None:
    sqlite3.connect(tmp_path / "sessions.db").close()
    sqlite3.connect(tmp_path / "events.db").close()

    report = repair(tmp_path)

    assert report.ok, report.errors
    assert repair_exit_code(report) == 0
    # The expected version comes from each file's owning module, not a literal:
    # a literal went stale the moment events.db gained the type index (R3-T8,
    # version 1 -> 2) and "repair migrates" is about reaching the current
    # version, not about the number happening to be 1.
    for name, table, version in (("sessions.db", "sessions", store_module._SCHEMA_VERSION),
                                 ("events.db", "events", events_module._SCHEMA_VERSION)):
        connection = sqlite3.connect(tmp_path / name)
        try:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == version
            found = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
        finally:
            connection.close()
        assert found == (table,)
    assert "not present (nothing to check)" in render_repair(report)


def test_repair_leaves_a_readable_provider_file_alone(tmp_path: Path) -> None:
    (tmp_path / "providers.json").write_text(
        '{"p1": {"id": "p1", "name": "Local", "base_url": "http://127.0.0.1:11434/v1"}}',
        encoding="utf-8",
    )

    report = repair(tmp_path)

    assert report.ok
    assert (tmp_path / "providers.json").exists()
    assert list(tmp_path.glob("providers.json.corrupt-*")) == []
    assert "readable (1 provider(s))" in render_repair(report)


def test_repair_quarantines_a_corrupt_provider_file_and_keeps_the_bytes(tmp_path: Path) -> None:
    original = b"{oops, this is not json"
    (tmp_path / "providers.json").write_bytes(original)

    report = repair(tmp_path)

    assert report.ok, report.errors
    assert repair_exit_code(report) == 0
    assert not (tmp_path / "providers.json").exists()
    quarantined = list(tmp_path.glob("providers.json.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == original
    rendered = render_repair(report)
    assert "quarantined to" in rendered
    assert "PROBLEM" in rendered


def test_repair_reports_a_corrupt_database_and_deletes_nothing(tmp_path: Path) -> None:
    damaged = b"this is not a database" * 64
    (tmp_path / "sessions.db").write_bytes(damaged)
    (tmp_path / "providers.json").write_text("{}", encoding="utf-8")

    report = repair(tmp_path)

    assert not report.ok
    assert repair_exit_code(report) == 1
    assert len(report.errors) == 1 and "integrity_check" in report.errors[0]
    assert (tmp_path / "sessions.db").read_bytes() == damaged
    assert "PROBLEM" in render_repair(report)
    assert "nothing was deleted" in render_repair(report)


def test_repair_reports_a_missing_workspace(tmp_path: Path) -> None:
    report = repair(tmp_path / "nowhere")

    assert not report.ok
    assert repair_exit_code(report) == 1
    assert "does not exist" in report.errors[0]

