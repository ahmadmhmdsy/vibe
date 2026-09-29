# services/vibe/src/vibe/executor/local.py
from __future__ import annotations
import asyncio, shutil, socket
from pathlib import Path
from vibe.models import ToolResult
from vibe.executor.base import DevServerHandle

def _pnpm() -> str:
    # Windows: pnpm is a .cmd shim on PATH; CreateProcess cannot launch a bare
    # "pnpm" (no PATHEXT resolution), so resolve the full path via shutil.which.
    return shutil.which("pnpm") or "pnpm"

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class LocalSubprocessExecutor:
    def __init__(self, workspace: Path, timeout: int = 120):
        self._workspace = workspace
        self._timeout = timeout
        self._dev_server: DevServerHandle | None = None
        self._pnpm = _pnpm()

    async def _run(self, cmd: list[str]) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=self._workspace,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            text = out.decode(errors="replace")[:20000]
            return ToolResult("", cmd[0], text, proc.returncode != 0)
        except asyncio.TimeoutError:
            return ToolResult("", cmd[0], "timeout", True)
        except Exception as e:
            return ToolResult("", cmd[0], str(e), True)

    async def install(self, packages: list[str]) -> ToolResult:
        return await self._run([self._pnpm, "install", *packages])

    async def build(self) -> ToolResult:
        return await self._run([self._pnpm, "run", "build"])

    @property
    def dev_server_url(self) -> str | None:
        return self._dev_server.url if self._dev_server else None

    async def start_dev_server(self) -> DevServerHandle:
        port = _free_port()
        proc = await asyncio.create_subprocess_exec(
            self._pnpm, "run", "dev", "--port", str(port), "--host", "127.0.0.1",
            cwd=self._workspace, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        self._dev_server = DevServerHandle(port=port, url=f"http://127.0.0.1:{port}/", process=proc)
        return self._dev_server

    async def stop_dev_server(self) -> None:
        if self._dev_server and self._dev_server.process.returncode is None:
            self._dev_server.process.terminate()
            try:
                await asyncio.wait_for(self._dev_server.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._dev_server.process.kill()
        self._dev_server = None

    async def read_console_logs(self, tail: int) -> str:
        # Playwright console buffer lands in Task 11; stub returns empty for now
        return ""

    async def screenshot(self) -> bytes:
        # Playwright screenshot lands in Task 11; stub returns empty for now
        return b""
