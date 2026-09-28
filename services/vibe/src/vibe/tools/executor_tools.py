# services/vibe/src/vibe/tools/executor_tools.py
from __future__ import annotations
from vibe.models import ToolSchema, ToolResult
from vibe.runtime.base import AgentContext

async def _install_deps(args, ctx):
    r = await ctx.executor.install(args.get("packages", []))
    return ToolResult("", "install_deps", r.content, r.is_error)

async def _build(args, ctx):
    r = await ctx.executor.build()
    return ToolResult("", "build", r.content, r.is_error)

async def _run_dev_server(args, ctx):
    h = await ctx.executor.start_dev_server()
    return ToolResult("", "run_dev_server", f"dev server at {h.url}")

async def _stop_dev_server(args, ctx):
    await ctx.executor.stop_dev_server()
    return ToolResult("", "stop_dev_server", "stopped")

async def _read_console_logs(args, ctx):
    logs = await ctx.executor.read_console_logs(args.get("tail", 50))
    return ToolResult("", "read_console_logs", logs)

async def _screenshot(args, ctx):
    data = await ctx.executor.screenshot()
    return ToolResult("", "screenshot", f"screenshot:{len(data)}:bytes")

def register_executor_tools(reg) -> None:
    reg.register("install_deps", ToolSchema("install_deps", "Install npm packages",
        {"type": "object", "properties": {"packages": {"type": "array", "items": {"type": "string"}}}, "required": ["packages"]}), _install_deps)
    reg.register("build", ToolSchema("build", "Build the project with vite",
        {"type": "object", "properties": {}}), _build)
    reg.register("run_dev_server", ToolSchema("run_dev_server", "Start the dev server",
        {"type": "object", "properties": {}}), _run_dev_server)
    reg.register("stop_dev_server", ToolSchema("stop_dev_server", "Stop the dev server",
        {"type": "object", "properties": {}}), _stop_dev_server)
    reg.register("read_console_logs", ToolSchema("read_console_logs", "Read browser console logs",
        {"type": "object", "properties": {"tail": {"type": "integer"}}}), _read_console_logs)
    reg.register("screenshot", ToolSchema("screenshot", "Capture a screenshot of the running app",
        {"type": "object", "properties": {}}), _screenshot)
