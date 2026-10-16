# services/vibe/src/vibe/tools/executor_tools.py
from __future__ import annotations

import base64

from vibe.executor.base import (
    CAPTURE_FAILED,
    NO_DEV_SERVER,
    NO_DRIVER,
    UNREACHABLE,
    capture_console,
    capture_screenshot,
)
from vibe.models import Attachment, ToolResult, ToolSchema
from vibe.supply_chain import is_allowlisted, request_approval


async def _install_deps(args, ctx):
    packages = args.get("packages", [])
    if not packages:
        return ToolResult("", "install_deps", "no packages specified", True)
    allowlisted = [p for p in packages if is_allowlisted(p)]
    extra = [p for p in packages if not is_allowlisted(p)]
    results: list[str] = []
    if allowlisted:
        r = await ctx.executor.install(allowlisted)
        results.append(r.content)
        if r.is_error:
            return ToolResult("", "install_deps", "\n".join(results), True)
    for pkg in extra:
        if ctx.approval_store is None or ctx.event_log is None:
            results.append(f"skipped {pkg} (approval unavailable)")
            continue
        status = await request_approval(ctx, [pkg])
        if status == "approved":
            r = await ctx.executor.install([pkg])
            results.append(r.content)
        else:
            results.append(f"skipped {pkg} (not approved)")
    return ToolResult("", "install_deps", "\n".join(results))

async def _build(args, ctx):
    r = await ctx.executor.build()
    return ToolResult("", "build", r.content, r.is_error)

async def _run_dev_server(args, ctx):
    h = await ctx.executor.start_dev_server()
    return ToolResult("", "run_dev_server", f"dev server at {h.url}")

async def _stop_dev_server(args, ctx):
    await ctx.executor.stop_dev_server()
    return ToolResult("", "stop_dev_server", "stopped")

#: What a tool tells the model when it cannot do its job. An empty string would
#: read as "the console was clean" or "a blank screenshot" -- a claim the
#: executor cannot make, and one the model would act on.
#:
#: The causes are kept distinct (BE-09). They used to be one message, so a user
#: whose dev server had died was told to install Playwright: a false diagnosis
#: that sends the model looking for an install instead of restarting the server.
#: Every message opens with "unavailable" -- the class of answer, which callers
#: and older tests match -- and then names the one thing that fixes this cause.
_UNAVAILABLE_WHY = {
    NO_DEV_SERVER: ("unavailable: no dev server is running, so there is no page to read: call"
                    " run_dev_server first and retry (nothing was read; this is not"
                    " a clean console)"),
    NO_DRIVER: ("unavailable: the dev server is running but this build has no"
                " browser driver, so it cannot read the console or take a"
                " screenshot (nothing was read; this is not a clean console)"),
    # A server that was started and then died still has a URL, so it used to be
    # reported as a missing driver -- the exact false diagnosis BE-09 is about.
    UNREACHABLE: ("unavailable: the dev server at {url} is not accepting connections - it has"
                  " probably stopped or crashed; call run_dev_server again (nothing was read;"
                  " this is not a clean console)"),
    CAPTURE_FAILED: ("unavailable: the page was reached but could not be inspected - read the"
                     " dev server output for the reason (nothing was read; this is not a"
                     " clean console)"),
}
#: The answer for an executor that cannot name its cause, and for a cause this
#: build does not know. "No driver" is what a None from those executors has always
#: meant, so it stays the conservative default.
_UNAVAILABLE = _UNAVAILABLE_WHY[NO_DRIVER]


def _why(status: str, url: str | None) -> str:
    return _UNAVAILABLE_WHY.get(status, _UNAVAILABLE).format(url=url or "?")


async def _read_console_logs(args, ctx):
    url = ctx.executor.dev_server_url
    capture = await capture_console(ctx.executor, url, tail=args.get("tail", 50),
                                    level=args.get("level", "error"))
    if not capture.ok:
        return ToolResult("", "read_console_logs", _why(capture.status, url))
    text = capture.value if isinstance(capture.value, str) else ""
    return ToolResult("", "read_console_logs", text)


async def _screenshot(args, ctx):
    url = ctx.executor.dev_server_url
    capture = await capture_screenshot(ctx.executor, url)
    if not capture.ok:
        return ToolResult("", "screenshot", _why(capture.status, url))
    # A capture that reports ok must carry PNG bytes; anything else is a broken
    # implementation, and "no driver" is the honest summary of "no image".
    data = capture.value if isinstance(capture.value, bytes) else None
    if data is None:
        return ToolResult("", "screenshot", _UNAVAILABLE)
    # The image travels as an attachment, which the registry turns into a content
    # block the model can see. The byte count in `content` is a label, not a
    # substitute: a model told `screenshot:5015:bytes` has seen nothing.
    return ToolResult("", "screenshot", f"captured {len(data)} bytes",
                      attachments=[Attachment("screenshot.png", "image/png",
                                              base64.b64encode(data).decode())])

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
        {"type": "object", "properties": {"tail": {"type": "integer"},
                                          "level": {"type": "string",
                                                     "enum": ["error", "warning", "all"]}}}),
        _read_console_logs)
    reg.register("screenshot", ToolSchema("screenshot", "Capture a screenshot of the running app",
        {"type": "object", "properties": {}}), _screenshot)
