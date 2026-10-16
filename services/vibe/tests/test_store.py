# tests/test_store.py
import pytest

from vibe.models import ModelRef
from vibe.store import SessionStore


@pytest.mark.asyncio
async def test_create_and_get_session(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    assert sid
    s = await store.get_session(sid)
    assert s.model_ref.provider_id == "openai"
    assert s.title  # auto-generated


@pytest.mark.asyncio
async def test_list_sessions(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    await store.create_session(ModelRef(provider_id="anthropic", model_id="claude-sonnet-4-6"))
    sessions = await store.list_sessions()
    assert len(sessions) == 2


@pytest.mark.asyncio
async def test_rename_and_delete_session(tmp_path):
    store = SessionStore(db_path=tmp_path / "test.db")
    sid = await store.create_session(ModelRef(provider_id="openai", model_id="gpt-4o"))
    await store.rename_session(sid, "My App")
    assert (await store.get_session(sid)).title == "My App"
    await store.delete_session(sid)
    assert await store.get_session(sid) is None
