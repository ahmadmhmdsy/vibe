# tests/test_run_registry.py
"""R1-T1: the one-run-per-session guard must be atomic (BE-04).

The route used to check runs.is_running(sid) and claim runs.start(sid) fifty
lines later, with six awaits in between. Two concurrent sends on one event loop
both passed the check and both ran the agent -- probe 4 measured two 200s and
two run() invocations. try_start makes the check and the claim one synchronous
step, so exactly one caller can win.
"""
import asyncio

import httpx
from conftest import swap

from vibe.runs import RunRegistry


def test_try_start_claims_once():
    reg = RunRegistry()
    first = reg.try_start("s1")
    assert first is not None
    assert reg.try_start("s1") is None


def test_try_start_allows_a_new_run_after_finish():
    reg = RunRegistry()
    first = reg.try_start("s1")
    assert first is not None
    reg.finish("s1", first)
    assert reg.try_start("s1") is not None


def test_concurrent_try_start_has_one_winner():
    """Eight threads race for the slot; exactly one wins."""
    reg = RunRegistry()

    async def race():
        return await asyncio.gather(*[asyncio.to_thread(reg.try_start, "s1") for _ in range(8)])

    winners = [h for h in asyncio.run(race()) if h is not None]
    assert len(winners) == 1


def test_an_aborted_handle_still_owns_the_slot():
    """Abort must not release the slot: the task may still be writing events.

    is_running reports False for an aborted handle, so using it as the guard
    would reopen the interleaving window this fix exists to close.
    """
    reg = RunRegistry()
    assert reg.try_start("s1") is not None
    reg.abort("s1")
    assert reg.is_running("s1") is False
    assert reg.try_start("s1") is None


async def test_two_concurrent_sends_run_the_agent_once(app, client, counting_runtime, session_id):
    """The route-level guard, over the ASGI app rather than the function."""
    swap(app, runtime=counting_runtime)

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        responses = await asyncio.gather(
            c.post(f"/sessions/{session_id}/messages", json={"content": "a"}),
            c.post(f"/sessions/{session_id}/messages", json={"content": "b"}),
        )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["error"]["code"] == "run_in_progress"
    assert counting_runtime.calls == 1
