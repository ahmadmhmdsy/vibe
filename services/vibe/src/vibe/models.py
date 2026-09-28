# services/vibe/src/vibe/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Any

Role = Literal["user", "assistant", "system", "tool"]

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class Message:
    role: Role
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False

@dataclass
class ModelRef:
    provider_id: str
    model_id: str

@dataclass
class AgentInput:
    session_id: str
    messages: list[Message]
    model: ModelRef

@dataclass
class AgentEvent:
    kind: Literal["text_chunk", "tool_call", "tool_result", "error", "turn_complete"]
    data: dict[str, Any]

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]

@dataclass
class ChatRequest:
    messages: list[Message]
    tools: list[ToolSchema]
    model: ModelRef
    temperature: float = 0.0

@dataclass
class ChatEvent:
    kind: Literal["text_chunk", "tool_call", "usage", "done"]
    data: dict[str, Any]

@dataclass
class UsageRecord:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    cache_hit: bool
    cache_hit_rate: float
    total_tokens: int
    cost_usd: float
