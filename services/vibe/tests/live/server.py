r"""Live bridge check — deterministic runtime, real ASGI/SSE stack.

Run it against a real server to prove the streaming and abort paths end to end
without needing an LLM:

    # terminal 1 (from services/vibe, venv python on PATH):
    $env:PYTHONPATH="src"; .venv\Scripts\python.exe tests/live/server.py
    # terminal 2:
    .venv\Scripts\python.exe tests/live/live.py

Evidence from the last run: artifacts/live-verification.txt
"""
import asyncio

import uvicorn

from vibe.api.app import create_app
from vibe.config import Settings
from vibe.container import Container
from vibe.models import AgentEvent


class StubRuntime:
    """Deterministic streaming runtime: no LLM, no network, real ASGI stack."""

    async def run(self, input, ctx):
        text = input.messages[-1].content if input.messages else ""
        if "abort-me" in text:
            yield AgentEvent(kind="text_chunk", data={"text": "partial "})
            await asyncio.sleep(0.1)
            yield AgentEvent(kind="text_chunk", data={"text": "work "})
            await asyncio.Event().wait()  # blocks until the run is cancelled
        for i in range(5):
            yield AgentEvent(kind="text_chunk", data={"text": f"tok{i} "})
            await asyncio.sleep(0.05)
        yield AgentEvent(kind="turn_complete", data={})


# The stub runtime is passed to the builder rather than patched in afterwards,
# so the lifecycle and the auto-run policies are composed with it too.
app = create_app(container=Container.build(Settings.from_env(), runtime=StubRuntime()))
uvicorn.run(app, host="127.0.0.1", port=7399, log_level="warning")
