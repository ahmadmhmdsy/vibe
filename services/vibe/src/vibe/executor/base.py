"""The executor seam.

`Executor` is the only executor type callers may depend on. `container.py` is
the one module allowed to import a concrete implementation
(`LocalSubprocessExecutor` today, a `DockerExecutor` later), which is what makes
swapping executors a one-file change instead of a refactor.
`tests/test_seams.py` enforces both halves of that sentence: no module outside
`executor/` (other than the container) imports a concrete class, and no route
ever names one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vibe.models import ToolResult


@dataclass
class DevServerHandle:
    port: int
    url: str
    process: object


#: Why a capture produced nothing. `read_console_logs` and `screenshot` answer
#: None for every cause at once, and the tools used to print one sentence for all
#: of them -- "no browser driver installed" -- so a user whose dev server had died
#: was sent to install Playwright. A caller that must tell the user what to fix
#: asks for the reason instead of guessing from None (BE-09).
OK = "ok"
NO_DEV_SERVER = "no-dev-server"
NO_DRIVER = "no-driver"
UNREACHABLE = "dev-server-unreachable"
CAPTURE_FAILED = "capture-failed"

#: Every reason that is not OK, in the order a user meets them.
CAUSES = (NO_DEV_SERVER, NO_DRIVER, UNREACHABLE, CAPTURE_FAILED)


@dataclass(frozen=True)
class Capture:
    """What a capture produced, or why it produced nothing.

    `value` is the console text for a console read and the PNG bytes for a
    screenshot. It is None for every status other than `ok`, and an empty string
    is a real answer: the page was read and printed nothing at that level.
    """

    status: str = OK
    value: str | bytes | None = None

    @property
    def ok(self) -> bool:
        return self.status == OK


async def capture_console(executor, url: str | None, *, tail: int = 200, level: str = "error") -> Capture:
    """Read the browser console through whichever API `executor` provides.

    An executor that answers with a `Capture` keeps the reason. One that only
    implements `read_console_logs` -- a test double, or an implementation that has
    not adopted this seam yet -- is reported as `no-driver`, which is exactly
    what its None has always meant, so callers can migrate one at a time without
    the answer changing meaning.
    """
    if url is None:
        return Capture(NO_DEV_SERVER)
    reason_aware = getattr(executor, "read_console", None)
    if reason_aware is not None:
        return await reason_aware(url, tail=tail, level=level)
    logs = await executor.read_console_logs(url, tail=tail, level=level)
    return Capture(OK, logs) if logs is not None else Capture(NO_DRIVER)


async def capture_screenshot(executor, url: str | None) -> Capture:
    """The same contract for screenshots; `value` is the PNG bytes."""
    if url is None:
        return Capture(NO_DEV_SERVER)
    reason_aware = getattr(executor, "capture_screenshot", None)
    if reason_aware is not None:
        return await reason_aware(url)
    data = await executor.screenshot(url)
    return Capture(OK, data) if data is not None else Capture(NO_DRIVER)


class Executor(Protocol):
    @property
    def dev_server_url(self) -> str | None: ...
    async def install(self, packages: list[str]) -> ToolResult: ...
    async def build(self) -> ToolResult: ...
    async def start_dev_server(self) -> DevServerHandle: ...
    async def stop_dev_server(self) -> None: ...
    # None means "this executor has no driver for it", which callers must not
    # read as "the console was clean" or "a blank screenshot".
    # An empty string means the page was read and printed nothing at that level.
    # "level" is "error" by default: a healthy app prints warnings all day, and
    # treating those as runtime errors would burn fix iterations on noise.
    async def read_console_logs(self, url: str, tail: int = 200, level: str = "error") -> str | None: ...
    async def screenshot(self, url: str) -> bytes | None: ...
    # The reason-aware form of the two calls above. Prefer these (through
    # capture_console/capture_screenshot, which fall back for executors that do
    # not implement them) whenever the answer reaches a user or the model.
    async def read_console(self, url: str, tail: int = 200, level: str = "error") -> Capture: ...
    async def capture_screenshot(self, url: str) -> Capture: ...
    async def close(self) -> None: ...
