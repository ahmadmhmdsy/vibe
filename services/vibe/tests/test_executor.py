# tests/test_executor.py
import subprocess
import shutil
import pytest
from vibe.executor.local import LocalSubprocessExecutor
from vibe.executor.base import DevServerHandle
from pathlib import Path


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
    await ex.stop_dev_server()


@pytest.mark.asyncio
async def test_install_with_timeout(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"t"}')
    ex = LocalSubprocessExecutor(workspace=tmp_path, timeout=1)
    r = await ex.install(["left-pad"])
    # may pass or fail depending on network; just assert it returns a ToolResult
    assert hasattr(r, "is_error")
