# tests/test_supply_chain.py
import asyncio

import pytest

from vibe.approvals import ApprovalStore
from vibe.events import EventBus, EventLog
from vibe.models import ToolResult
from vibe.runtime.base import AgentContext
from vibe.store import SessionStore
from vibe.supply_chain import is_allowlisted
from vibe.tools.executor_tools import register_executor_tools
from vibe.tools.registry import ToolRegistry


class MockExecutor:
    def __init__(self):
        self.installed: list[str] = []

    async def install(self, packages):
        self.installed.extend(packages)
        return ToolResult("", "install", f"installed {packages}")


def _ctx(tmp_path, ex, log, bus, approvals):
    return AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=ex,
        event_bus=bus,
        store=SessionStore(db_path=tmp_path / "t.db"),
        event_log=log,
        approval_store=approvals,
    )


def test_is_allowlisted():
    assert is_allowlisted("react")
    assert is_allowlisted("react@^19.0.0")
    assert is_allowlisted("vite")
    assert is_allowlisted("@vitejs/plugin-react")
    assert not is_allowlisted("date-fns")
    assert not is_allowlisted("lodash")


@pytest.mark.asyncio
async def test_install_allowlisted_needs_no_approval(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = MockExecutor()
    ctx = _ctx(tmp_path, ex, EventLog(), EventBus(), ApprovalStore())
    r = await reg.execute("install_deps", {"packages": ["react"]}, ctx)
    assert r.is_error is False
    assert "react" in ex.installed
    assert ctx.approval_store.list("s1") == []


@pytest.mark.asyncio
async def test_install_non_allowlisted_requires_approval(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = MockExecutor()
    approvals = ApprovalStore()
    ctx = _ctx(tmp_path, ex, EventLog(), EventBus(), approvals)
    task = asyncio.create_task(reg.execute("install_deps", {"packages": ["date-fns"]}, ctx))
    await asyncio.sleep(0.2)
    # Not installed yet — waiting for approval.
    assert ex.installed == []
    pending = approvals.list("s1")
    assert len(pending) == 1
    # Approve → install proceeds.
    approvals.resolve(pending[0].id, True)
    r = await task
    assert r.is_error is False
    assert "date-fns" in ex.installed


@pytest.mark.asyncio
async def test_install_non_allowlisted_denied_skips(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = MockExecutor()
    approvals = ApprovalStore()
    ctx = _ctx(tmp_path, ex, EventLog(), EventBus(), approvals)
    task = asyncio.create_task(reg.execute("install_deps", {"packages": ["date-fns"]}, ctx))
    await asyncio.sleep(0.2)
    pending = approvals.list("s1")
    approvals.resolve(pending[0].id, False)
    r = await task
    assert "date-fns" not in ex.installed
    assert "skipped" in r.content


# --- R1-T4: promoted from the 2026-10-11 review (probe 2, BE-02) ---
#
# is_allowlisted truncates at the first "@", so "react@npm:evil-package" is
# judged by the name "react" while npm installs evil-package. The cases below
# are the specifiers that ride the allowlist today; the already-rejected ones
# sit beside them so the boundary is pinned in one place.

ALLOWED_SPECIFIERS = [
    "react",
    "react@^19",
    "react@19.0.0",
    "@types/react",
    "@types/react@^19",
    "@vitejs/plugin-react",
    "zustand@^5",
]

DENIED_SPECIFIERS = ["evil-package", "react-malicious", "", " ", "../evil", "@scope", "date-fns", "lodash"]

# "react@^19 nope" is not a real version range. It is here because the obvious
# fix -- rejecting an alias/protocol prefix -- would still let it resolve to the
# allowlisted name "react", so R2-T2 also refuses range characters that can
# never be part of a version we accept.
BYPASS_SPECIFIERS = [
    "react@npm:evil-package",  # alias installs something else entirely
    "react@npm:@evil/pkg",  # alias to a scoped package
    "@types/react@npm:evil",  # scoped alias
    "react@github:evil/repo",  # git protocol
    "react@git+https://evil/x.git",
    "react@file:../evil",  # local path
    "react@link:../evil",
    "react@http://evil/x.tgz",
    "react@workspace:*",
    "react@^19 nope",
]


@pytest.mark.parametrize("spec", ALLOWED_SPECIFIERS)
def test_allowlisted_specifiers(spec):
    assert is_allowlisted(spec) is True


@pytest.mark.parametrize("spec", DENIED_SPECIFIERS)
def test_denied_specifiers(spec):
    assert is_allowlisted(spec) is False


@pytest.mark.parametrize("spec", BYPASS_SPECIFIERS)
def test_alias_and_protocol_specifiers_are_denied(spec):
    assert is_allowlisted(spec) is False
