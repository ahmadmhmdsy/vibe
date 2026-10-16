# services/vibe/src/vibe/executor/local.py
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import shutil
import signal
import socket
import time
from collections import deque
from pathlib import Path

from vibe import registry as registry_probe
from vibe.executor.base import NO_DEV_SERVER, Capture, DevServerHandle
from vibe.executor.browser import BrowserDriver
from vibe.maintenance import (
    DEV_SERVERS_NAME,
    DevServerEntry,
    forget_dev_server,
    record_dev_server,
)
from vibe.models import ToolResult

logger = logging.getLogger(__name__)

# How much dev-server stdout to keep. It exists only to keep the pipe drained
# and to aid debugging; it is not the browser console (see read_console_logs).
_CONSOLE_BUFFER_LINES = 500

#: Packages whose install-time build script is safe enough to approve without
#: asking. pnpm 12 blocks every dependency's build script by default
#: (ERR_PNPM_IGNORED_BUILDS); a scaffolded project approves none, so an install
#: that pulls one in -- esbuild, through vite -- exits 1 until it is approved.
#: ponytail: one entry, the case actually hit. Add a name here only after
#: reviewing its script; anything else stays blocked and the failure names it.
SAFE_BUILD_SCRIPTS = ("esbuild",)

_IGNORED_BUILDS_HINT = (
    "\n\npnpm blocked a dependency's install script that is not on the safe "
    "list (ERR_PNPM_IGNORED_BUILDS). If you trust it, add it under "
    "`allowBuilds:` in pnpm-workspace.yaml, then install again."
)


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
    def __init__(
        self,
        workspace: Path,
        timeout: int = 120,
        *,
        browser: BrowserDriver | None = None,
        probe: registry_probe.RegistryProbe | None = None,
        state_file: Path | None = None,
    ):
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
        # Shared by default: the answer is about the machine, not this session,
        # so the second session must not pay for the same 5-second probe.
        self._probe = probe if probe is not None else registry_probe.DEFAULT
        # The pidfile lives beside the session workspaces, not inside one: a
        # session workspace is a directory under the workspace root
        # (services/sessions.py), so its parent is the root. Overridable for a
        # caller that lays them out differently.
        self._state_root = Path(state_file).parent if state_file is not None else Path(workspace).parent
        self._state_file = Path(state_file) if state_file is not None else self._state_root / DEV_SERVERS_NAME

    async def _run(self, cmd: list[str]) -> ToolResult:
        try:
            # Its own process group, so a POSIX tree kill can target the whole
            # subtree without signalling us. Ignored on Windows.
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self._workspace,
                start_new_session=True,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            text = out.decode(errors="replace")[:20000]
            return ToolResult("", cmd[0], text, proc.returncode != 0)
        except TimeoutError:
            # wait_for cancelled communicate(); without this the install/build is
            # left running with no reference to it (probe 5).
            logger.warning("%s timed out after %ss", cmd[0], self._timeout)
            await self._kill_tree(proc)
            return ToolResult("", cmd[0], "timeout", True)
        except Exception as e:
            logger.warning("%s failed to run: %s", cmd[0], e)
            return ToolResult("", cmd[0], str(e), True)

    async def _kill_tree(self, proc: asyncio.subprocess.Process) -> None:
        """Kill a process and its descendants.

        pnpm is a shim that spawns node, so killing the shim leaves the real work
        running -- the leak behind both the timeout and a dev server that keeps
        its port. taskkill /T walks the tree on Windows; POSIX gets the process
        group created by start_new_session.
        """
        if proc.returncode is not None:
            return
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            try:
                pgid = os.getpgid(proc.pid)
                # Never signal our own group: if the child was somehow not given
                # its own session, killpg would take the server down with it.
                if pgid != os.getpgid(0):
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            proc.kill()

    async def install(self, packages: list[str]) -> ToolResult:
        # R5-T8: an offline machine is told so in seconds. pnpm would otherwise
        # spend the whole timeout and then fail with output whose last lines name
        # no cause the user can act on -- install, network, or version conflict.
        if not await self._probe.probe():
            return ToolResult("", "install", registry_probe.OFFLINE_MESSAGE, True)
        self._approve_safe_build_scripts()
        result = await self._run([self._pnpm, "install", *packages])
        if result.is_error and "ERR_PNPM_IGNORED_BUILDS" in result.content:
            result = ToolResult("", "install", result.content + _IGNORED_BUILDS_HINT, True)
        return result

    def _approve_safe_build_scripts(self) -> None:
        """Approve known-safe install scripts so pnpm 12 does not block them.

        pnpm 12 refuses to run any dependency's build script until it is
        approved; a scaffolded project approves none, so an install that pulls
        in esbuild (through vite) exits 1 with ERR_PNPM_IGNORED_BUILDS. This
        writes the approval the repo root already carries into the session
        workspace -- but only when the project has no pnpm-workspace.yaml of its
        own, because that file is the project's and overwriting it would drop
        the user's settings.
        """
        config = self._workspace / "pnpm-workspace.yaml"
        if config.exists():
            return
        body = "".join(
            [
                "# written by vibe so pnpm may run known-safe install scripts\n",
                "allowBuilds:\n",
                *(f"  {name}: true\n" for name in SAFE_BUILD_SCRIPTS),
            ]
        )
        try:
            config.write_text(body, encoding="utf-8")
        except OSError as e:
            # The install can still succeed if nothing needs a build script; a
            # config we could not write is a warning, not a failed install.
            logger.warning("could not write %s: %s", config, e)

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
            self._pnpm,
            "run",
            "dev",
            "--port",
            str(port),
            "--strictPort",
            "--host",
            "127.0.0.1",
            cwd=self._workspace,
            env=env,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # The pipe is drained continuously. An unread PIPE fills its kernel buffer
        # and the child then blocks on write, so the dev server silently freezes
        # the first time it prints more than that buffer holds.
        self._drain_task = asyncio.create_task(self._drain(proc))
        await self._remember(port, proc.pid)
        logger.info("dev server started on port %s (pid %s)", port, proc.pid)
        return DevServerHandle(port=port, url=f"http://127.0.0.1:{port}/", process=proc)

    async def _remember(self, port: int, pid: int) -> None:
        """Record the server, so a crash leaves the next run something to reap."""
        entry = DevServerEntry(
            workspace=str(self._workspace),
            pid=pid,
            port=port,
            started_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        )
        try:
            await asyncio.to_thread(record_dev_server, self._state_root, entry)
        except OSError as e:
            # A pidfile is a convenience for the next run, never a reason to fail
            # this one: the dev server is already up.
            logger.warning("could not record the dev server in %s: %s", self._state_file, e)

    async def _forget(self) -> None:
        """Drop this workspace's entry once its server has stopped."""
        try:
            await asyncio.to_thread(forget_dev_server, self._state_root, str(self._workspace))
        except OSError as e:
            logger.warning("could not update %s: %s", self._state_file, e)

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

    async def read_console(self, url: str, tail: int = 200, level: str = "error") -> Capture:
        """The console and, when there is none, why it could not be read.

        `url is None` is this executor's own answer -- no dev server was started,
        so there is nothing to look at. Every other cause belongs to the browser
        driver to judge (a missing browser, an unreachable page, a failed
        capture), and conflating the two told users to install Playwright for a
        dev server that had simply died (BE-09).
        """
        if url is None:
            return Capture(NO_DEV_SERVER)
        return await self._browser.read_console(url, tail=tail, level=level)

    async def screenshot(self, url: str) -> bytes | None:
        """A screenshot of the running app, or None when no driver can take one."""
        if url is None:
            return None
        return await self._browser.screenshot(url)

    async def capture_screenshot(self, url: str) -> Capture:
        """A screenshot and, when there is none, why -- see `read_console`."""
        if url is None:
            return Capture(NO_DEV_SERVER)
        return await self._browser.capture_screenshot(url)

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

        killed = True
        if proc is not None and proc.returncode is None:
            logger.info("stopping dev server (pid %s)", proc.pid)
            try:
                # The whole tree, never terminate() on the shim. pnpm is a
                # wrapper around node, so terminating it returns immediately
                # while the real vite process lives on -- orphaned, still
                # holding the port and every file in the workspace, so
                # DELETE /sessions/{id} could never move the workspace aside
                # (measured: the node child outlived the stop by 15+ minutes and
                # the port stayed bound). The tree walk has to happen while the
                # shim is alive, because taskkill /T only reaches live children.
                await self._kill_tree(proc)
            except OSError as e:
                # A missing taskkill must not turn a delete into a 500: keep the
                # pidfile entry so the next run's reap still has a handle on it.
                killed = False
                logger.warning("could not stop dev server pid %s: %s", proc.pid, e)

        # Forgetting is one-way: the entry is the next run's only handle on an
        # orphan, so it is dropped only once the process is gone.
        if killed:
            await self._forget()

    async def close(self) -> None:
        """Release the browser. The dev server is stopped separately.

        The two are independent: restarting a dev server must not restart the
        browser, and a browser left open outlives the process that started it.
        """
        await self.stop_dev_server()
        await self._browser.close()
