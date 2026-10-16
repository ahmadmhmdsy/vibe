# tests/test_registry_keys.py
"""R6-T5 (L-5): in-process registries are keyed by (owner, session).

Three maps decide what a session is doing right now: the run registry (which run
is in flight), the executor registry (one dev-server process per session) and the
autorun policy registry. All three used the bare session id as the key, which is
only correct while exactly one user exists. Two owners with the same session id
would share a run handle, a dev server and a policy -- and the second owner's
abort would cancel the first owner's work.

The key is a value object so that "owner + session" cannot be passed in the wrong
order and so a future move to a real multi-tenant deployment is a change of the
key's *source*, not of every dict in the process.

Behaviour for the single local user is unchanged, and that is asserted too: the
owner argument defaults to the loopback owner, so every existing call site keeps
working and every existing test still describes the path that runs in production.
"""
from __future__ import annotations

import asyncio
import contextlib

from vibe.auth import LOOPBACK_OWNER_ID
from vibe.runs import RunRegistry, SessionKey


def test_the_key_is_owner_then_session() -> None:
    key = SessionKey(owner_id="alice", session_id="s1")
    assert (key.owner_id, key.session_id) == ("alice", "s1")
    assert key == SessionKey(owner_id="alice", session_id="s1")
    assert key != SessionKey(owner_id="bob", session_id="s1")
    # Hashable, because it is a dict key.
    assert {key: 1}[SessionKey(owner_id="alice", session_id="s1")] == 1


def test_two_owners_with_the_same_session_id_do_not_collide() -> None:
    runs = RunRegistry()
    alice = runs.try_start("s1", owner_id="alice")
    assert alice is not None
    # The whole point: the same session id is free for a different owner.
    bob = runs.try_start("s1", owner_id="bob")
    assert bob is not None
    assert bob is not alice
    # ...but a second run for the same owner and session is still refused.
    assert runs.try_start("s1", owner_id="alice") is None
    assert runs.is_running("s1", owner_id="alice") is True
    assert runs.is_running("s1", owner_id="bob") is True

    # Aborting one owner's run must leave the other's alone.
    alice.request_abort()
    assert runs.is_running("s1", owner_id="alice") is False
    assert runs.is_running("s1", owner_id="bob") is True

    # And finishing one frees only that owner's slot.
    runs.finish("s1", bob, owner_id="bob")
    assert runs.is_running("s1", owner_id="bob") is False
    assert runs.get("s1", owner_id="bob") is None


def test_the_loopback_owner_is_the_default_key() -> None:
    runs = RunRegistry()
    handle = runs.try_start("s1")
    assert handle is not None
    # The default and the explicit loopback owner are the same slot...
    assert runs.try_start("s1", owner_id=LOOPBACK_OWNER_ID) is None
    assert runs.is_running("s1") is True
    # ...and a different owner is a different slot.
    assert runs.is_running("s1", owner_id="alice") is False
    assert runs.get("s1") is handle


async def test_abort_can_only_reach_the_named_owners_run() -> None:
    runs = RunRegistry()
    alice = runs.try_start("s1", owner_id="alice")
    bob = runs.try_start("s1", owner_id="bob")
    # A live task, because that is what the chat route attaches and the only
    # thing request_abort can actually cancel.
    alive = asyncio.create_task(asyncio.sleep(3600))
    bob.task = alive
    try:
        assert runs.abort("s1", owner_id="bob") is True
        assert alive.cancelling() == 1
        assert runs.is_running("s1", owner_id="bob") is False
        # Alice's run is untouched: same session id, different owner.
        assert runs.is_running("s1", owner_id="alice") is True
        assert alice.abort_requested is False
        assert runs.abort("nobody", owner_id="alice") is False
    finally:
        alive.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await alive


def test_the_executor_registry_separates_owners(container) -> None:
    workspace = container.settings.workspace_dir
    alice = container.get_executor("s1", workspace, owner_id="alice")
    bob = container.get_executor("s1", workspace, owner_id="bob")
    local = container.get_executor("s1", workspace)

    assert alice is not bob, "two owners shared one dev-server process"
    assert local is not alice
    # Same owner, same session: the process is reused, not restarted.
    assert container.get_executor("s1", workspace, owner_id="alice") is alice
    assert container.get_autorun("s1", workspace, owner_id="alice") is not bob


def test_the_autorun_registry_separates_owners(container) -> None:
    workspace = container.settings.workspace_dir
    alice = container.get_autorun("s1", workspace, owner_id="alice")
    bob = container.get_autorun("s1", workspace, owner_id="bob")
    assert alice is not bob
    assert container.get_autorun("s1", workspace, owner_id="alice") is alice
