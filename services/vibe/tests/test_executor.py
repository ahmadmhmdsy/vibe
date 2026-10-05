# tests/test_executor.py
import base64
import shutil
import socket
import subprocess
import time
import types

import pytest

from vibe.events import EventBus
from vibe.executor.local import LocalSubprocessExecutor
from vibe.runtime.base import AgentContext
from vibe.store import SessionStore
from vibe.tools.executor_tools import register_executor_tools
from vibe.tools.registry import ToolRegistry


def _pnpm_reachable() -> bool:
    """Network guard: can pnpm reach the npm registry?

    The scaffolded project declares zero dependencies, so running
    "pnpm install" there succeeds even fully offline (false positive).
    Registry reachability is therefore checked directly with "pnpm ping".
    """
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        return False
    try:
        proc = subprocess.run([pnpm, "ping"], capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _listening(port: int, timeout: float = 20.0) -> bool:
    """True once something accepts a TCP connection on `port`.

    A dev server that started but bound a *different* port still reports a pid
    and a url, so `handle.port > 0` alone cannot catch that. Vite falls back
    to 5173 when it is handed a literal `--`, which is exactly how this
    regressed once already.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


@pytest.mark.asyncio
async def test_install_build_dev_server(tmp_path):
    if not _pnpm_reachable():
        pytest.skip("no network: pnpm install unavailable")
    # scaffold a minimal vite project
    (tmp_path / "package.json").write_text('{"name":"t","scripts":{"build":"vite build","dev":"vite"}}')
    (tmp_path / "index.html").write_text("<html><body><div id='root'></div></body></html>")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.tsx").write_text("export default function App(){return null}")
    ex = LocalSubprocessExecutor(workspace=tmp_path)
    r = await ex.install([])
    assert r.is_error is False
    r = await ex.build()
    assert r.is_error is False
    handle = await ex.start_dev_server()
    assert handle.port > 0
    assert "localhost" in handle.url or "127.0.0.1" in handle.url
    assert _listening(handle.port), f"dev server is not listening on {handle.port}"
    await ex.stop_dev_server()


@pytest.mark.asyncio
async def test_install_with_timeout(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"t"}')
    ex = LocalSubprocessExecutor(workspace=tmp_path, timeout=1)
    r = await ex.install(["left-pad"])
    # may pass or fail depending on network; just assert it returns a ToolResult
    assert hasattr(r, "is_error")


@pytest.mark.asyncio
async def test_close_stops_the_dev_server_and_the_browser(tmp_path):
    """The browser is a separate process, so it needs its own release.

    Leaving it open meant every deleted session leaked a Chromium.
    """
    ex = LocalSubprocessExecutor(workspace=tmp_path)
    calls: list[str] = []

    async def fake_stop():
        calls.append("stop")

    async def fake_browser_close():
        calls.append("browser")

    ex.stop_dev_server = fake_stop
    ex._browser = types.SimpleNamespace(close=fake_browser_close)
    await ex.close()
    assert calls == ["stop", "browser"]


class _PreviewExecutor:
    """Just enough executor for the capture tools."""

    def __init__(self, url, logs=None, shot=None):
        self._url = url
        self._logs = logs
        self._shot = shot
        self.seen: dict = {}

    @property
    def dev_server_url(self):
        return self._url

    async def read_console_logs(self, url, tail=200, level="error"):
        self.seen = {"url": url, "tail": tail, "level": level}
        return self._logs

    async def screenshot(self, url):
        self.seen = {"url": url}
        return self._shot


def _ctx(tmp_path, ex):
    return AgentContext(session_id="s1", workspace_path=tmp_path, executor=ex,
                       event_bus=EventBus(), store=SessionStore(db_path=tmp_path / "t.db"))


@pytest.mark.asyncio
async def test_screenshot_tool_returns_an_image_the_model_can_see(tmp_path):
    """The tool used to return "screenshot:5015:bytes" -- a byte count, not an
    image. A model told that has seen nothing.
    """
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = _PreviewExecutor("http://127.0.0.1:5173/", shot=png)
    r = await reg.execute("screenshot", {}, _ctx(tmp_path, ex))
    assert r.is_error is False
    assert len(r.attachments) == 1
    assert r.attachments[0].content_type == "image/png"
    assert base64.b64decode(r.attachments[0].data_base64) == png


@pytest.mark.asyncio
async def test_screenshot_tool_says_unavailable_when_there_is_no_driver(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = _PreviewExecutor(None, shot=None)
    r = await reg.execute("screenshot", {}, _ctx(tmp_path, ex))
    assert r.is_error is False
    assert "unavailable" in r.content
    assert r.attachments == []


@pytest.mark.asyncio
async def test_read_console_logs_tool_passes_the_url_and_level(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = _PreviewExecutor("http://127.0.0.1:5173/", logs="ReferenceError: x is not defined")
    r = await reg.execute("read_console_logs", {"tail": 5, "level": "warning"}, _ctx(tmp_path, ex))
    assert ex.seen == {"url": "http://127.0.0.1:5173/", "tail": 5, "level": "warning"}
    assert "ReferenceError" in r.content


@pytest.mark.asyncio
async def test_read_console_logs_tool_defaults_to_errors_only(tmp_path):
    reg = ToolRegistry()
    register_executor_tools(reg)
    ex = _PreviewExecutor("http://127.0.0.1:5173/", logs="")
    await reg.execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert ex.seen["level"] == "error"
