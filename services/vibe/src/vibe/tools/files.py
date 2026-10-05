# services/vibe/src/vibe/tools/files.py
from __future__ import annotations

from pathlib import Path

from vibe.models import ToolResult, ToolSchema
from vibe.workspace import relative_files


def _safe_path(workspace: Path, relpath: str) -> Path | None:
    p = (workspace / relpath).resolve()
    if not p.is_relative_to(workspace.resolve()):
        return None
    return p

async def _write_file(args, ctx):
    p = _safe_path(ctx.workspace_path, args["path"])
    if p is None:
        return ToolResult("", "write_file", "path outside workspace", True)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(args["content"], encoding="utf-8")
    return ToolResult("", "write_file", f"wrote {args['path']}")

async def _read_file(args, ctx):
    p = _safe_path(ctx.workspace_path, args["path"])
    if p is None or not p.exists():
        return ToolResult("", "read_file", "file not found", True)
    return ToolResult("", "read_file", p.read_text(encoding="utf-8")[:20000])

async def _edit_file(args, ctx):
    p = _safe_path(ctx.workspace_path, args["path"])
    if p is None or not p.exists():
        return ToolResult("", "edit_file", "file not found", True)
    text = p.read_text(encoding="utf-8")
    if args["old_string"] not in text:
        return ToolResult("", "edit_file", "old_string not found", True)
    p.write_text(text.replace(args["old_string"], args["new_string"], 1), encoding="utf-8")
    return ToolResult("", "edit_file", f"edited {args['path']}")

async def _list_files(args, ctx):
    # Vendored trees are pruned during the walk: an agent asking for the file
    # list should not receive thousands of node_modules paths.
    files = relative_files(ctx.workspace_path)
    return ToolResult("", "list_files", "\n".join(files[:200]))

def register_file_tools(reg) -> None:
    reg.register("write_file", ToolSchema("write_file", "Write a file in the workspace",
        {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}), _write_file)
    reg.register("read_file", ToolSchema("read_file", "Read a file from the workspace",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}), _read_file)
    reg.register("edit_file", ToolSchema("edit_file", "Edit a file in the workspace",
        {"type": "object", "properties": {"path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}},
        "required": ["path", "old_string", "new_string"]}), _edit_file)
    reg.register("list_files", ToolSchema("list_files", "List files in the workspace",
        {"type": "object", "properties": {}}), _list_files)
