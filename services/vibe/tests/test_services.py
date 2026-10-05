# tests/test_services.py
import pytest

from vibe.events import EventLog
from vibe.models import ModelRef
from vibe.services.messages import MessageService
from vibe.services.sessions import SessionService
from vibe.store import SessionStore, title_from_text


class _Lifecycle:
    """Only delete() is called by the service under test."""

    def __init__(self):
        self.deleted = []

    async def delete(self, sid):
        self.deleted.append(sid)


def _service(tmp_path):
    return SessionService(store=None, lifecycle=_Lifecycle(), workspace_dir=tmp_path)


# --- path confinement ------------------------------------------------------

def test_resolve_file_accepts_a_path_inside_the_workspace(tmp_path):
    svc = _service(tmp_path)
    p = svc.resolve_file("s1", "src/main.py")
    assert p == (tmp_path / "s1" / "src" / "main.py").resolve()


def test_resolve_file_rejects_dot_dot_escaping_the_workspace(tmp_path):
    svc = _service(tmp_path)
    assert svc.resolve_file("s1", "../other-session/secret.py") is None
    assert svc.resolve_file("s1", "src/../../escape.py") is None


def test_resolve_file_rejects_an_absolute_path_outside(tmp_path):
    svc = _service(tmp_path)
    assert svc.resolve_file("s1", str(tmp_path / "other" / "f.py")) is None


def test_resolve_file_rejects_a_symlink_escaping_the_workspace(tmp_path):
    """resolve() follows symlinks, so a link inside the workspace that points out
    must still be refused — the check is on the resolved path, not the literal one."""
    svc = _service(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    ws = tmp_path / "s1"
    ws.mkdir()
    (ws / "link.txt").symlink_to(outside)
    assert svc.resolve_file("s1", "link.txt") is None


# --- read / write ----------------------------------------------------------

def test_write_then_read_round_trips(tmp_path):
    svc = _service(tmp_path)
    svc.write_text("s1", "src/main.py", "print('hi')")
    assert svc.read_text("s1", "src/main.py") == "print('hi')"


def test_ensure_workspace_creates_the_directory(tmp_path):
    svc = _service(tmp_path)
    ws = svc.ensure_workspace("s1")
    assert ws == tmp_path / "s1"
    assert ws.is_dir()
    # Idempotent: a second call returns the same path without error.
    assert svc.ensure_workspace("s1") == ws


def test_write_creates_parent_directories(tmp_path):
    svc = _service(tmp_path)
    svc.write_text("s1", "a/b/c.txt", "x")
    assert (tmp_path / "s1" / "a" / "b" / "c.txt").read_text() == "x"


def test_read_missing_file_raises_file_not_found(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(FileNotFoundError):
        svc.read_text("s1", "nope.txt")


def test_read_refuses_a_path_outside_the_workspace(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(FileNotFoundError):
        svc.read_text("s1", "../outside.txt")


def test_write_refuses_a_path_outside_the_workspace(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(ValueError, match="outside workspace"):
        svc.write_text("s1", "../outside.txt", "x")
    assert not (tmp_path / "outside.txt").exists()


def test_delete_goes_through_the_lifecycle_not_the_store(tmp_path):
    """A session owns more than its row; the service must not delete the row alone."""
    lifecycle = _Lifecycle()
    svc = SessionService(store=None, lifecycle=lifecycle, workspace_dir=tmp_path)

    import asyncio
    asyncio.run(svc.delete("s1"))
    assert lifecycle.deleted == ["s1"]


# --- history projection ----------------------------------------------------

async def test_history_projects_user_and_assistant_turns():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "hello"})
    await log.append("s1", "assistant/message", {"content": "hi"})
    msgs = await MessageService(log).history("s1")
    assert [(m.role, m.content) for m in msgs] == [("user", "hello"), ("assistant", "hi")]


async def test_history_skips_events_that_are_not_messages():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "hi"})
    await log.append("s1", "tool_call", {"name": "read_file"})
    await log.append("s1", "text_chunk", {"text": "partial"})
    msgs = await MessageService(log).history("s1")
    assert [(m.role, m.content) for m in msgs] == [("user", "hi")]


async def test_history_maps_an_error_turn_to_the_assistant_role():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "hi"})
    await log.append("s1", "assistant/error", {"content": "OPENAI_API_KEY is not configured."})
    msgs = await MessageService(log).history("s1")
    assert [(m.role, m.content) for m in msgs] == [
        ("user", "hi"),
        ("assistant", "OPENAI_API_KEY is not configured."),
    ]


async def test_history_skips_a_message_with_no_content():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "hi"})
    await log.append("s1", "assistant/message", {"content": ""})
    msgs = await MessageService(log).history("s1")
    assert [(m.role, m.content) for m in msgs] == [("user", "hi")]


async def test_history_is_empty_for_an_unknown_session():
    assert await MessageService(EventLog()).history("nope") == []


# --- pagination -------------------------------------------------------------

async def test_history_returns_the_most_recent_messages_by_default():
    log = EventLog()
    for i in range(5):
        await log.append("s1", "user/message", {"content": f"m{i}"})
    msgs = await MessageService(log).history("s1", limit=2)
    assert [m.content for m in msgs] == ["m3", "m4"]


async def test_history_offset_pages_backwards_from_the_latest():
    log = EventLog()
    for i in range(5):
        await log.append("s1", "user/message", {"content": f"m{i}"})
    msgs = await MessageService(log).history("s1", limit=2, offset=2)
    assert [m.content for m in msgs] == ["m1", "m2"]


async def test_history_offset_beyond_the_first_message_is_empty():
    log = EventLog()
    await log.append("s1", "user/message", {"content": "m0"})
    assert await MessageService(log).history("s1", limit=10, offset=5) == []


async def test_page_reports_the_total_and_whether_older_messages_remain():
    log = EventLog()
    for i in range(5):
        await log.append("s1", "user/message", {"content": f"m{i}"})
    svc = MessageService(log)

    latest = await svc.page("s1", limit=2)
    assert [m.content for m in latest.messages] == ["m3", "m4"]
    assert latest.total == 5
    assert latest.has_more is True

    oldest = await svc.page("s1", limit=2, offset=4)
    assert [m.content for m in oldest.messages] == ["m0"]
    assert oldest.has_more is False


# --- session titles ---------------------------------------------------------

def test_title_from_text_collapses_whitespace_and_truncates():
    assert title_from_text("  build   a\n  todo app  ") == "build a todo app"
    assert title_from_text("x" * 200) == "x" * 59 + "…"


def test_title_from_text_is_empty_for_a_blank_message():
    assert title_from_text("   \n  ") == ""


async def test_retitle_replaces_the_placeholder(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    try:
        sid = await store.create_session(ModelRef("openai", "gpt-4o"))
        assert (await store.get_session(sid)).title == f"Untitled {sid[:4]}"
        assert await store.retitle_from_message(sid, "build a todo app") is True
        assert (await store.get_session(sid)).title == "build a todo app"
    finally:
        store.close()


async def test_retitle_never_clobbers_a_manual_rename(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    try:
        sid = await store.create_session(ModelRef("openai", "gpt-4o"))
        await store.rename_session(sid, "My app")
        assert await store.retitle_from_message(sid, "build a todo app") is False
        assert (await store.get_session(sid)).title == "My app"
    finally:
        store.close()


async def test_retitle_ignores_a_blank_message(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    try:
        sid = await store.create_session(ModelRef("openai", "gpt-4o"))
        assert await store.retitle_from_message(sid, "   ") is False
        assert (await store.get_session(sid)).title == f"Untitled {sid[:4]}"
    finally:
        store.close()
