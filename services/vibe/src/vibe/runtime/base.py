# services/vibe/src/vibe/runtime/base.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, AsyncIterator
from vibe.models import AgentInput, AgentEvent
from vibe.executor.base import Executor
from vibe.events import EventBus
from vibe.store import SessionStore

@dataclass
class AgentContext:
    session_id: str
    workspace_path: Path
    executor: Executor
    event_bus: EventBus
    store: SessionStore

class AgentRuntime(Protocol):
    async def run(self, input: AgentInput, ctx: AgentContext) -> AsyncIterator[AgentEvent]: ...
