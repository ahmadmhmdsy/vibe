# services/vibe/src/vibe/runtime/base.py
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vibe.approvals import ApprovalStore
from vibe.events import EventBus, EventStore
from vibe.executor.base import Executor
from vibe.models import AgentEvent, AgentInput
from vibe.store import SessionStore


@dataclass
class AgentContext:
    session_id: str
    workspace_path: Path
    executor: Executor
    event_bus: EventBus
    store: SessionStore
    event_log: EventStore | None = None
    approval_store: ApprovalStore | None = None
    #: Answers "did the user press Stop?". The chat route supplies it so the
    #: auto-fix loop can stop between iterations instead of editing files behind
    #: a turn the user already cancelled.
    is_aborted: Callable[[], bool] | None = None


class AgentRuntime(Protocol):
    async def run(self, input: AgentInput, ctx: AgentContext) -> AsyncIterator[AgentEvent]: ...
