# tests/test_executor_timeout.py
"""R1-T2: a timeout must kill the process tree, not just abandon it (BE-05).

Review probe 5 showed a pnpm-shaped process still running after _run gave up on
it: wait_for(proc.communicate()) is cancelled, proc is dropped, and nothing ever
signals it. The grandchild below is the honest test -- it outlives a kill of its
parent, so only a tree kill passes.
"""
import sys
import time

import pytest

from vibe.executor.local import LocalSubprocessExecutor


@pytest.mark.asyncio
async def test_timeout_leaves_no_live_process(tmp_path):
    marker = tmp_path / "still-alive"
    # The parent spawns a grandchild that writes the marker after the parent is
    # gone, so killing only the parent leaves the marker behind.
    inner = f"import time,pathlib;time.sleep(3);pathlib.Path(r'{marker}').write_text('alive')"
    script = f"import subprocess,time;subprocess.Popen([{sys.executable!r},'-c',{inner!r}]);time.sleep(30)"
    ex = LocalSubprocessExecutor(tmp_path, timeout=1)
    result = await ex._run([sys.executable, "-c", script])
    assert result.is_error and result.content == "timeout"
    time.sleep(4)
    assert not marker.exists(), "the grandchild outlived the timeout"
