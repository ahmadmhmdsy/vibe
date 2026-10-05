# services/vibe/src/vibe/executor/local.py
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import socket
import time
from collections import deque
from pathlib import Path

from vibe.executor.base import DevServerHandle
from vibe.executor.browser import BrowserDriver
from vibe.models import ToolResult

logger = logging.getLogger(__name__)

# How much dev-server stdout to keep. It exists only to keep the pipe drained
# and to aid debugging; it is not the browser console (see read_console_logs).
_CONSOLE_BUFFER_LINES = 500


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
    def __init__(self, workspace: Path, timeout: int = 120, *, browser: BrowserDriver | None = None):
        self._workspace = workspace
        self._timeout = timeout
        self._dev_server: DevServerHandle | None = None
        self._pnpm = _pnpm()
        self._console: deque[str] = deque(maxlen=_CONSOLE_BUFFER_LINES)
        self._drain_task: asyncio.Task | None = None
        self._last_used: time.monotonic()
        # The browser is a separate process from the dev server, so it is owned
        # here rather than started and stopped with it. Injectable so a test can
        # supply a stub without a browser installed.
        self._browser = browser if browser is not None else BrowserDriver()

    async def _run(self, cmd: list[str]) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=self._workspace,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            text = out.decode(errors="replace")[:20000]
            return ToolResult("", cmd[0], text, proc.returncode != 0)
        except TimeoutError:
            logger.warning("%s timed out after %ss", cmd[0], self._timeout)
            return ToolResult("", cmd[0], "timeout", True)
        except Exception as e:
            logger.warning("%s failed to run: %s", cmd[0], e)
            return ToolResult("", cmd[0], str(e), True)

    async def install(self, packages: list[str]) -> ToolResult:
        return await self._run([self._pnpm, "install", *packages])

    async def build(self) -> ToolResult:
        return await self._run([self._pnpm, "run", "build"])

    @property
    def dev_server_url(self) -> str | None:
        if self._dev_server is None:
            return None
        self._touch()
        return self._dev_server.url

    def _touch(self) -> None:
        self._last_used = time.monotonic()

    async def start_dev_server(self) -> DevServerHandle:
        # Restarting used to overwrite the handle without stopping the previous
        # process, leaking one `pnpm dev` per restart.
        if self._dev_server is not None:
            await self.stop_dev_server()
        self._touch()
        self._dev_server = await self._spawn()
        return self._dev_server

    async def _spawn(self) -> DevServerHandle:
        port = _free_port()
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["CI"] = "1"
        # No "--" separator: pnpm 12 forwards it to the script as a literal
        # argument, and Vite then ignores --port and falls back to 5173 - so
        # every session collided on the default port and `dev_server_url` named
        # a port nothing was listening on.
        proc = await asyncio.create_subprocess_exec(
            self._pnpm, "run", "dev", "--port", str(port), "--strictPort",
            "--host", "127.0.0.1",
            cwd=self._workspace,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # The pipe is drained continuously. An unread PIPE fills its kernel buffer
        # and the child then blocks on write, so the dev server silently freezes
        # the first time it prints more than that buffer holds.
        self._drain_task = asyncio.create_task(self._drain(proc))
        logger.info("dev server started on port %s (pid %s)", port, proc.pid)
        return DevServerHandle(port=port, url=f"http://127.0.0.1:{port}/", process=proc)

    async def _drain(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        try:
            async for line in proc.stdout:
                self._console.append(line)
        except asyncio.CancelledError:
            raise

    async def read_console_logs(self, url: str, tail: int = 200, level: str = "error") -> str | None:
        """Browser console output, or None when no driver can supply it.

        This returns None rather than an empty string. The dev server's stdout is
        captured into `_console` to keep the pipe drained, but it is *not* the
        browser console: Vite prints a startup banner on every start, so treating
        it as console output would make the autorun runtime-error check fire on a
        healthy app and burn fix iterations.
        """
        if url is None:
            return None
        return await self._browser.read_console_logs(url, tail=tail, level=level)

    async def screenshot(self, url: str) -> bytes | None:
        """A screenshot of the running app, or None when no driver can take one."""
        if url is None:
            return None
        return await self._browser.screenshot(url)

    def is_idle(self, timeout_min: int) -> bool:
        """True if a dev server is running and has not been used for the timeout.

        A non-positive timeout disables reaping rather than stopping every dev
        server on the first pass.
        """
        if self._dev_server is None or timeout_min <= 0:
            return False
        return (time.monotonic() - self._last_used) > timeout_min * 60

    async def stop_if_idle(self, timeout_min: int) -> bool:
        """Stop the dev server if it has been idle. True if one was stopped."""
        if not self.is_idle(timeout_min):
            return False
        await self.stop_dev_server()
        return True

    async def stop_dev_server(self) -> None:
        if self._dev_server is None:
            return
        proc = self._dev_server.process
        self._dev_server = None

        if self._drain_task is not None:
            self._drain_task.cancel()
            await asyncio.gather(self._drain_task, return_exceptions=True)
            self._drain_task = None

        if proc is None or proc.returncode is not None:
            return
        logger.info("stopping dev server (pid %s)", proc.pid)
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            # SIGTERM was ignored; escalate rather than leak the process.
            logger.warning("dev server pid %s ignored terminate; killing", proc.pid)
            proc.kill()
            await proc.wait()

    async def close(self) -> None:
        """Release the browser. The dev server is stopped separately.

        The two are independent: restarting a dev server must not restart the
        browser, and a browser left open outlives the process that started it.
        """
        await self.stop_dev_server()
        await self._browser.close()
