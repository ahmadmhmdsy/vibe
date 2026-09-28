# services/vibe/src/vibe/tools/registry.py
from __future__ import annotations
from typing import Any, Callable, Awaitable
from vibe.models import ToolSchema, ToolResult
from vibe.runtime.base import AgentContext

Handler = Callable[[dict[str, Any], AgentContext], Awaitable[ToolResult]]

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
        from langchain_core.tools import Tool
        tools = []
        for name, (schema, handler) in self._tools.items():
            tools.append(Tool.from_function(
                name=name, description=schema.description,
                coroutine=lambda args, h=handler, c=ctx: h(args, c),
                args_schema=schema.parameters,
            ))
        return tools
