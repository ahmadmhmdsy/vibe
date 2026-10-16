# services/vibe/src/vibe/tools/registry.py
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from vibe.models import ToolResult, ToolSchema
from vibe.runtime.base import AgentContext

Handler = Callable[[dict[str, Any], AgentContext], Awaitable[ToolResult]]


def _payload(result: ToolResult) -> tuple[Any, dict[str, Any]]:
    """Split a ToolResult into (model-visible content, artifact metadata).

    LangChain stringifies whatever a tool returns, so returning the dataclass
    handed the model `ToolResult(tool_call_id='', name=..., content=...)` -- a Python
    repr -- instead of the tool's actual output, and dropped `is_error` on the
    floor. The content-and-artifact response format fixes both: the model gets
    the content, and the metadata rides in `ToolMessage.artifact`, where the
    runtime can read it and the model never does.
    """
    if result.attachments:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": result.content}]
        blocks.extend(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{a.content_type};base64,{a.data_base64}"},
            }
            for a in result.attachments
        )
        content: Any = blocks
    else:
        content = result.content
    return content, {
        "name": result.name,
        "is_error": result.is_error,
        "attachments": len(result.attachments),
    }


def _adapt_handler(handler: Handler, ctx: AgentContext) -> Callable[..., Awaitable[tuple[Any, dict[str, Any]]]]:
    """Adapt a (args, ctx) handler to a StructuredTool function.

    StructuredTool passes the LLM's arguments as keyword arguments, while the
    handler protocol takes a single args dict. Collecting **kwargs into one dict
    keeps every input shape working: no-arg tools (LLM passes {}), optional
    args, and multi-arg calls all arrive intact. Plain Tool.from_function
    cannot do this — it treats a single-parameter function as single-input
    and rejects any call whose argument count is not exactly one.
    """

    async def run(**kwargs: Any) -> tuple[Any, dict[str, Any]]:
        return _payload(await handler(kwargs, ctx))

    return run


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[ToolSchema, Handler]] = {}

    def register(self, name: str, schema: ToolSchema, handler: Handler) -> None:
        self._tools[name] = (schema, handler)

    def schemas(self) -> list[ToolSchema]:
        return [s for s, _ in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any], ctx: AgentContext) -> ToolResult:
        if name not in self._tools:
            return ToolResult(tool_call_id="", name=name, content=f"unknown tool: {name}", is_error=True)
        _, handler = self._tools[name]
        return await handler(arguments, ctx)

    def to_langchain_tools(self, ctx: AgentContext) -> list:
        from langchain_core.tools import StructuredTool

        tools = []
        for name, (schema, handler) in self._tools.items():
            tools.append(
                StructuredTool.from_function(
                    name=name,
                    description=schema.description,
                    func=_adapt_handler(handler, ctx),
                    coroutine=_adapt_handler(handler, ctx),
                    args_schema=schema.parameters,
                    # See _payload: without this the model receives a repr.
                    response_format="content_and_artifact",
                )
            )
        return tools
