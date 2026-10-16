"""Read-only probes for the 2026-10-11 app review.

Each probe exercises real production code and prints an observable result.
Nothing here writes to the app; the only side effects are inside temp dirs.
"""
import asyncio
import contextlib
import logging
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "services" / "vibe" / "src"))

import httpx
from fastapi.testclient import TestClient

from vibe.api.app import create_app
from vibe.config import Settings
from vibe.container import Container
from vibe.events import EventBus, EventLog
from vibe.models import AgentEvent
from vibe.store import SessionStore
from vibe.supply_chain import is_allowlisted
from vibe.tools.files import register_file_tools
from vibe.tools.registry import ToolRegistry

logging.getLogger("vibe").setLevel(logging.CRITICAL)


class StubRuntime:
    async def run(self, input, ctx):
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


class CapturingRuntime:
    def __init__(self):
        self.seen = []

    async def run(self, input, ctx):
        self.seen.append([(m.role, m.content) for m in input.messages])
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


class SlowRuntime:
    def __init__(self, delay=0.4):
        self.delay = delay
        self.started = 0

    async def run(self, input, ctx):
        self.started += 1
        await asyncio.sleep(self.delay)
        yield AgentEvent(kind="text_chunk", data={"text": "slow"})
        yield AgentEvent(kind="turn_complete", data={})


def build(tmp, runtime):
    settings = Settings(workspace_dir=Path(tmp) / "ws", port=8000)
    registry = ToolRegistry()
    register_file_tools(registry)
    return create_app(settings, container=Container.build(
        settings,
        store=SessionStore(db_path=Path(tmp) / "sessions.db"),
        event_log=EventLog(),
        event_bus=EventBus(),
        runtime=runtime,
        tool_registry=registry,
    ))


@contextlib.contextmanager
def client_for(tmp, runtime, *, raise_server_exceptions=False):
    app = build(tmp, runtime)
    with TestClient(app, raise_server_exceptions=raise_server_exceptions) as c:
        yield c, app.state.container


def tmpdir():
    return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def hdr(name):
    print("\n" + "=" * 78 + "\n" + name + "\n" + "=" * 78)


def protected(label, fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"[{label}] probe raised: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
def probe1():
    hdr("PROBE 1 - unvalidated request bodies: does a missing field 500?")
    with tmpdir() as tmp, client_for(tmp, StubRuntime()) as (c, _):
        sid = c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
        for label, meth, url, body in [
            ("POST /sessions body={}", "post", "/sessions", {}),
            ("POST /sessions body={model:{}}", "post", "/sessions", {"model": {}}),
            ("POST /sessions body={model:{a:1}}", "post", "/sessions", {"model": {"a": 1}}),
            ("POST messages body={}", "post", f"/sessions/{sid}/messages", {}),
            ("PATCH session body={model:{}}", "patch", f"/sessions/{sid}", {"model": {}}),
            ("POST providers body={}", "post", "/providers", {}),
        ]:
            r = getattr(c, meth)(url, json=body)
            print(f"{label:36s} -> HTTP {r.status_code}  {r.text[:90]}")


# --------------------------------------------------------------------------
def probe2():
    hdr("PROBE 2 - supply-chain allowlist: does an npm alias bypass it?")
    for spec in ["react", "react@^19", "react@npm:evil-package", "react@github:evil/repo",
                 "react@file:../evil", "@scope/pkg", "@scope/pkg@^1"]:
        print(f"is_allowlisted({spec!r:26s}) = {is_allowlisted(spec)}")


# --------------------------------------------------------------------------
def probe3():
    hdr("PROBE 3 - conversation memory: what history reaches the model?")
    with tmpdir() as tmp, client_for(tmp, CapturingRuntime()) as (c, _):
        rt = c.app.state.container.runtime
        sid = c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
        c.post(f"/sessions/{sid}/messages", json={"content": "my name is Ahmad"})
        c.post(f"/sessions/{sid}/messages", json={"content": "what is my name?"})
        print("model calls seen:", len(rt.seen))
        for i, msgs in enumerate(rt.seen):
            print(f"  run {i}: messages handed to the model = {msgs}")
        print("history the UI can read:", c.get(f"/sessions/{sid}/messages").json())


# --------------------------------------------------------------------------
async def probe4():
    hdr("PROBE 4 - concurrent send race: does the 409 guard hold?")
    with tmpdir() as tmp:
        rt = SlowRuntime(delay=0.4)
        app = build(tmp, rt)
        container = app.state.container
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})
                sid = resp.json()["id"]
                r1, r2 = await asyncio.gather(
                    c.post(f"/sessions/{sid}/messages", json={"content": "first"}),
                    c.post(f"/sessions/{sid}/messages", json={"content": "second"}),
                )
                print("run() invocations:", rt.started)
                print("statuses:", sorted([r1.status_code, r2.status_code]),
                      "-> an atomic guard would give exactly one 200 and one 409")
        finally:
            container.store.close()
            container.event_log.close()


# --------------------------------------------------------------------------
async def probe5():
    hdr("PROBE 5 - executor timeout: is the child process killed?")
    from vibe.executor.local import LocalSubprocessExecutor
    with tmpdir() as tmp:
        marker = Path(tmp) / "child-survived.txt"
        code = ("import time, pathlib; time.sleep(3); "
                f"pathlib.Path(r'{marker}').write_text('alive')")
        ex = LocalSubprocessExecutor(workspace=Path(tmp), timeout=1)
        r = await ex._run([sys.executable, "-c", code])
        print("tool result:", r.content.strip(), "| is_error:", r.is_error)
        await asyncio.sleep(3.5)
        print("child still alive 3.5s after the 1s timeout?", marker.exists())


# --------------------------------------------------------------------------
def probe6():
    hdr("PROBE 6 - VIBE_HOST warning: does formatting the log record raise?")
    class CaptureHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.errors = []
            self.formatted = []
        def emit(self, record):
            try:
                self.formatted.append(record.getMessage())
            except Exception as e:  # noqa: BLE001
                self.errors.append(repr(e))

    with tmpdir() as tmp:
        app = create_app(Settings(host="0.0.0.0", workspace_dir=Path(tmp) / "ws"))
        lg = logging.getLogger("vibe.api.app")
        cap = CaptureHandler()
        lg.addHandler(cap)
        try:
            with TestClient(app, raise_server_exceptions=False):
                pass
        finally:
            lg.removeHandler(cap)
        print("formatting errors raised:", cap.errors)
        print("records that formatted cleanly:", [f[:70] for f in cap.formatted])


# --------------------------------------------------------------------------
async def probe7():
    hdr("PROBE 7 - failed workspace move during delete: is the session left half-torn-down?")
    with tmpdir() as tmp:
        app = build(tmp, StubRuntime())
        container = app.state.container
        try:
            with TestClient(app, raise_server_exceptions=False) as c:
                sid = c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]
                c.post(f"/sessions/{sid}/messages", json={"content": "remember this"})
                ws = container.session_service.workspace_path(sid)
                ws.mkdir(parents=True, exist_ok=True)
                events_before = len(await container.event_log.get(sid))
                held = open(ws / "held.txt", "w")  # noqa: SIM115
                held.write("locked"); held.flush()
                try:
                    await container.lifecycle.delete(sid)
                    print("delete succeeded (rename was not blocked on this platform)")
                except Exception as e:  # noqa: BLE001
                    print("delete raised:", type(e).__name__, str(e)[:80])
                finally:
                    held.close()
                session_after = await container.store.get_session(sid)
                events_after = len(await container.event_log.get(sid))
                print("session row still present after failed delete?", session_after is not None)
                print(f"events before={events_before} after={events_after}")
        finally:
            container.store.close()
            container.event_log.close()


def main():
    for name, fn in [("1", probe1), ("2", probe2), ("3", probe3), ("6", probe6)]:
        protected(name, fn)
    for name, fn in [("4", probe4), ("5", probe5), ("7", probe7)]:
        protected(name, lambda fn=fn: asyncio.run(fn()))
    print("\nDONE")


main()
