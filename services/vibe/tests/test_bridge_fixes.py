# tests/test_bridge_fixes.py
"""Regression tests for the frontend/backend bridge review findings.

Each test names the defect it pins: a silent field drop, a Stop button that
stopped nothing, a resume cursor reset to zero, a per-model breakdown that was
hardcoded empty, or an unknown session id that looked like a new one.
"""
import asyncio

import pytest
from conftest import swap

from vibe.api.errors import ApiError, ErrorCode
from vibe.api.routes.chat import abort_run, send_message
from vibe.models import AgentEvent, ModelRef, UsageRecord
from vibe.usage.tracker import UsageTracker


class BlockingRuntime:
    """Streams one chunk, then blocks until something cancels it."""

    def __init__(self):
        self.started = asyncio.Event()
        self.completed = False

    async def run(self, input, ctx):
        yield AgentEvent(kind="text_chunk", data={"text": "partial"})
        self.started.set()
        await asyncio.Event().wait()
        self.completed = True
        yield AgentEvent(kind="turn_complete", data={})


class FailingRuntime:
    def __init__(self, exc):
        self._exc = exc

    async def run(self, input, ctx):
        raise self._exc
        yield  # pragma: no cover - unreachable, makes this an async generator


class _Request:
    def __init__(self, app, query_params=None):
        self.app = app
        self.query_params = query_params or {}


def _new_sid(client):
    return client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]


# --- provider writes ------------------------------------------------------

def test_provider_patch_persists_camel_case_fields(client):
    created = client.post("/providers", json={
        "name": "Local", "baseUrl": "http://old.example/v1", "apiKey": "sk-one",
        "models": [{"id": "m1", "name": "M1", "protocol": "openai-chat"}],
    }).json()
    assert created["baseUrl"] == "http://old.example/v1"
    assert created["key_configured"] is True

    resp = client.patch(f"/providers/{created['id']}", json={
        "name": "Local 2", "baseUrl": "http://new.example/v1", "apiKey": "sk-two",
        "models": [{"id": "m2", "name": "M2", "protocol": "openai-chat"}],
    })
    assert resp.status_code == 200
    assert resp.json()["baseUrl"] == "http://new.example/v1"
    assert resp.json()["name"] == "Local 2"

    # The write has to survive a re-read, not just look right in the response.
    listed = {p["id"]: p for p in client.get("/providers").json()}
    assert listed[created["id"]]["baseUrl"] == "http://new.example/v1"
    assert listed[created["id"]]["models"] == [{"id": "m2", "name": "M2", "protocol": "openai-chat"}]


def test_provider_patch_accepts_snake_case(client):
    created = client.post("/providers", json={"name": "S", "baseUrl": "http://a/v1", "models": []}).json()
    resp = client.patch(f"/providers/{created['id']}", json={"base_url": "http://b/v1"})
    assert resp.status_code == 200
    assert resp.json()["baseUrl"] == "http://b/v1"


def test_provider_create_rejects_missing_fields(client):
    assert client.post("/providers", json={"name": "x"}).status_code == 400


def test_provider_patch_rejects_unknown_fields(client):
    created = client.post("/providers", json={"name": "S", "baseUrl": "http://a/v1", "models": []}).json()
    assert client.patch(f"/providers/{created['id']}", json={"nope": 1}).status_code == 400


# --- stopping a run -------------------------------------------------------

@pytest.mark.asyncio
async def test_abort_cancels_the_running_turn(app):
    runtime = BlockingRuntime()
    swap(app, runtime=runtime)
    sid = await app.state.container.store.create_session(ModelRef("openai", "gpt-4o"))

    task = asyncio.create_task(send_message(sid, {"content": "build it"}, app.state.container))
    await asyncio.wait_for(runtime.started.wait(), timeout=2)
    assert app.state.container.runs.is_running(sid)

    assert await abort_run(sid, app.state.container) == {"aborted": True}
    result = await asyncio.wait_for(task, timeout=2)

    assert result["aborted"] is True
    assert runtime.completed is False           # the run really stopped
    assert not app.state.container.runs.is_running(sid)   # and the registry was cleaned up
    types = [e.type for e in await app.state.container.event_log.get(sid)]
    assert "turn/aborted" in types
    assert "assistant/message" in types         # partial text is kept, not discarded


@pytest.mark.asyncio
async def test_abort_without_a_run_is_a_noop(app):
    sid = await app.state.container.store.create_session(ModelRef("openai", "gpt-4o"))
    assert await abort_run(sid, app.state.container) == {"aborted": False}


@pytest.mark.asyncio
async def test_abort_404_for_unknown_session(app):
    with pytest.raises(ApiError) as err:
        await abort_run("nope", app.state.container)
    assert err.value.status == 404
    assert err.value.code is ErrorCode.SESSION_NOT_FOUND


@pytest.mark.asyncio
async def test_second_send_while_running_is_rejected(app):
    runtime = BlockingRuntime()
    swap(app, runtime=runtime)
    sid = await app.state.container.store.create_session(ModelRef("openai", "gpt-4o"))

    task = asyncio.create_task(send_message(sid, {"content": "one"}, app.state.container))
    await asyncio.wait_for(runtime.started.wait(), timeout=2)
    with pytest.raises(ApiError) as err:
        await send_message(sid, {"content": "two"}, app.state.container)
    assert err.value.status == 409
    assert err.value.code is ErrorCode.RUN_IN_PROGRESS

    await abort_run(sid, app.state.container)
    await asyncio.wait_for(task, timeout=2)


# --- stream sequencing ----------------------------------------------------

def test_streamed_chunks_carry_a_real_seq_without_being_logged(client, app):
    sid = _new_sid(client)
    subscription = app.state.container.event_bus.subscribe(sid)
    assert client.post(f"/sessions/{sid}/messages", json={"content": "hi"}).status_code == 200

    published = subscription.pending()
    chunk = next(e for e in published if e.type == "text_chunk")
    assert chunk.seq > 0    # a zero here reset the client's resume cursor every chunk
    assert next(e for e in published if e.type == "turn_complete").seq > chunk.seq

    # The bus mirrors the log: a second tab sees the question, not just the answer.
    assert [e.type for e in published] == ["user/message", "text_chunk", "turn_complete", "assistant/message"]
    assert [e.seq for e in published] == [1, 2, 3, 4]

    stored = asyncio.run(app.state.container.event_log.get(sid))
    assert [e.type for e in stored] == ["user/message", "assistant/message"]
    assert [e.seq for e in stored] == [1, 4]     # chunk and turn_complete took 2 and 3
    asyncio.run(subscription.aclose())


def test_failed_run_records_an_error_turn(client, app):
    swap(app, runtime=FailingRuntime(ValueError("OPENAI_API_KEY is not configured.")))
    sid = _new_sid(client)
    assert client.post(f"/sessions/{sid}/messages", json={"content": "hi"}).status_code == 400

    history = client.get(f"/sessions/{sid}/messages").json()
    assert history[0] == {"role": "user", "content": "hi"}
    assert history[1]["role"] == "assistant"
    assert "OPENAI_API_KEY" in history[1]["content"]


# --- session identity -----------------------------------------------------

def test_unknown_session_is_a_404(client):
    assert client.get("/sessions/nope").status_code == 404
    assert client.get("/sessions/nope/messages").status_code == 404
    assert client.get("/sessions/nope/approvals").status_code == 404
    assert client.get("/sessions/nope/usage").status_code == 404
    assert client.get("/sessions/nope/files").status_code == 404
    assert client.patch("/sessions/nope", json={"title": "x"}).status_code == 404


def test_unknown_session_is_a_404_on_preview_too(client, app):
    """Preview used to mkdir a workspace for whatever id it was handed."""
    ws = app.state.container.settings.workspace_dir
    assert client.get("/sessions/nope/preview").status_code == 404
    assert client.post("/sessions/nope/preview/run").status_code == 404
    assert client.post("/sessions/nope/preview/stop").status_code == 404
    assert not (ws / "nope").exists()


def test_preview_state_for_a_real_session(client):
    sid = _new_sid(client)
    resp = client.get(f"/sessions/{sid}/preview")
    assert resp.status_code == 200
    assert resp.json() == {"url": None, "is_running": False}


def test_known_empty_session_still_returns_empty_collections(client):
    sid = _new_sid(client)
    assert client.get(f"/sessions/{sid}/messages").json() == []
    assert client.get(f"/sessions/{sid}/approvals").json() == []
    assert client.get(f"/sessions/{sid}/files").json() == []


# --- workspace listing ----------------------------------------------------

def test_file_listing_prunes_vendored_dirs(client, app):
    sid = _new_sid(client)
    ws = app.state.container.settings.workspace_dir / sid
    for rel in ("src/App.tsx", "node_modules/left-pad/index.js", "dist/bundle.js", ".venv/lib/site.py"):
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    assert client.get(f"/sessions/{sid}/files").json() == ["src/App.tsx"]


# --- usage ----------------------------------------------------------------

def _record(app, sid, **kw):
    defaults = {"cached_tokens": 0, "cache_write_tokens": 0, "cache_hit": False,
                "cache_hit_rate": 0.0, "cost_usd": 0.0}
    defaults.update(kw)
    return app.state.container.usage.record(sid, UsageRecord(**defaults))


def test_usage_reports_per_model_breakdown(client, app):
    # The conftest fixture swaps in a fresh EventLog, so rewire the tracker to it.
    swap(app, usage=UsageTracker(log=app.state.container.event_log, bus=app.state.container.event_bus))
    sid = _new_sid(client)

    async def seed():
        await _record(app, sid, provider="openai", model="gpt-4o",
                      input_tokens=100, output_tokens=50, cached_tokens=20,
                      cache_write_tokens=7, total_tokens=150, cost_usd=0.01)
        await _record(app, sid, provider="openai", model="gpt-4o",
                      input_tokens=10, output_tokens=5, cache_write_tokens=3, total_tokens=15)
        await _record(app, sid, provider="anthropic", model="claude",
                      input_tokens=1, output_tokens=1, total_tokens=2)
    asyncio.run(seed())

    body = client.get(f"/sessions/{sid}/usage").json()
    assert body["steps"] == 3
    assert body["total_cache_write_tokens"] == 10      # was hardcoded 0
    assert body["total_tokens"] == 167

    by_model = {f"{m['provider']}/{m['model']}": m for m in body["by_model"]}
    assert set(by_model) == {"openai/gpt-4o", "anthropic/claude"}   # was hardcoded []
    assert by_model["openai/gpt-4o"]["steps"] == 2
    assert by_model["openai/gpt-4o"]["total_tokens"] == 165
    assert by_model["openai/gpt-4o"]["cache_write_tokens"] == 10
    assert by_model["anthropic/claude"]["total_tokens"] == 2
