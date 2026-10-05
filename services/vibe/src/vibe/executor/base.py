from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vibe.models import ToolResult


@dataclass
class DevServerHandle:
    port: int
    url: str
    process: object

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
    async def close(self) -> None: ...
