# services/vibe/src/vibe/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "system", "tool"]

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class Attachment:
    """An image attached to a message (reference design, screenshot feedback)."""
    name: str
    content_type: str  # e.g. "image/png"
    data_base64: str


@dataclass
class Message:
    role: Role
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    attachments: list[Attachment] = field(default_factory=list)

@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False
    #: Images the tool wants the model to see. They travel beside `content` rather
    #: than inside it: the registry turns them into LangChain content blocks, and
    #: they are deliberately kept out of the SSE event payload (a base64 PNG in
    #: every stream frame would dwarf the rest of the transcript).
    attachments: list[Attachment] = field(default_factory=list)

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
