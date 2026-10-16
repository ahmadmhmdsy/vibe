# tests/test_browser_tools.py
"""BE-09: a missing dev server and a missing browser driver are different
failures and must not share one message.

`read_console_logs` and `screenshot` return None for both causes, and the tool
collapsed them into "no browser driver". A user whose dev server had died was
therefore told to install Playwright.
"""

import logging

import pytest

from vibe.events import EventBus
from vibe.executor.base import (
    CAPTURE_FAILED,
    NO_DEV_SERVER,
    NO_DRIVER,
    UNREACHABLE,
    Capture,
    capture_console,
)
from vibe.models import ToolResult
from vibe.runtime.base import AgentContext
from vibe.store import SessionStore
from vibe.tools.executor_tools import register_executor_tools
from vibe.tools.registry import ToolRegistry


class FakeExecutor:
    """An executor whose two failure causes are set independently."""

    def __init__(self, *, url=None, logs=None, data=None):
        self._url = url
        self._logs = logs
        self._data = data
        self.console_calls = 0
        self.screenshot_calls = 0

    @property
    def dev_server_url(self):
        return self._url

    async def read_console_logs(self, url, tail: int = 50, level: str = "error"):
        self.console_calls += 1
        return self._logs

    async def screenshot(self, url):
        self.screenshot_calls += 1
        return self._data


def _ctx(tmp_path, executor):
    return AgentContext(
        session_id="s1",
        workspace_path=tmp_path,
        executor=executor,
        event_bus=EventBus(),
        store=SessionStore(db_path=tmp_path / "t.db"),
    )


def _registry():
    reg = ToolRegistry()
    register_executor_tools(reg)
    return reg


# --- the tool message -------------------------------------------------------


@pytest.mark.asyncio
async def test_console_logs_without_a_dev_server_blame_the_dev_server(tmp_path):
    ex = FakeExecutor(url=None)
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert "dev server" in r.content
    assert "run_dev_server" in r.content
    assert "browser driver" not in r.content, "the driver is not the problem here"
    assert ex.console_calls == 0, "there is no page to read without a server"


@pytest.mark.asyncio
async def test_console_logs_with_a_server_but_no_driver_blame_the_driver(tmp_path):
    ex = FakeExecutor(url="http://127.0.0.1:5173/", logs=None)
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert "browser driver" in r.content
    # The distinction is the fix the model is sent to look for. This message may
    # say the server is running (it is); it must not tell the model to start one.
    assert "run_dev_server" not in r.content
    assert "no dev server is running" not in r.content
    assert ex.console_calls == 1


@pytest.mark.asyncio
async def test_console_logs_are_returned_verbatim_when_read(tmp_path):
    ex = FakeExecutor(url="http://127.0.0.1:5173/", logs="boom")
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert r.content == "boom"


@pytest.mark.asyncio
async def test_screenshot_without_a_dev_server_blame_the_dev_server(tmp_path):
    ex = FakeExecutor(url=None)
    r = await _registry().execute("screenshot", {}, _ctx(tmp_path, ex))
    assert "dev server" in r.content
    assert "run_dev_server" in r.content
    assert "browser driver" not in r.content
    assert ex.screenshot_calls == 0


@pytest.mark.asyncio
async def test_screenshot_with_a_server_but_no_driver_blame_the_driver(tmp_path):
    ex = FakeExecutor(url="http://127.0.0.1:5173/", data=None)
    r = await _registry().execute("screenshot", {}, _ctx(tmp_path, ex))
    assert "browser driver" in r.content
    assert "run_dev_server" not in r.content
    assert "no dev server is running" not in r.content
    assert ex.screenshot_calls == 1


# --- the autorun runtime-error check ----------------------------------------


class FakeBuildExecutor:
    """Enough executor for AutoRunPolicy.maybe_run: build ok, server "running"."""

    def __init__(self, *, url):
        self._url = url
        self.reads = 0

    @property
    def dev_server_url(self):
        return self._url

    async def build(self):
        return ToolResult("", "build", "")

    async def start_dev_server(self):
        return None

    async def read_console_logs(self, url, tail: int = 50, level: str = "error"):
        self.reads += 1
        return None


@pytest.mark.asyncio
async def test_autorun_names_the_missing_dev_server_in_its_log(tmp_path, caplog):
    from vibe.autorun.policy import AutoRunPolicy

    ex = FakeBuildExecutor(url=None)
    policy = AutoRunPolicy(executor=ex, runtime=None, max_fix_iterations=3)
    with caplog.at_level(logging.WARNING, logger="vibe.autorun.policy"):
        await policy.maybe_run(_ctx(tmp_path, ex), ["App.tsx"])
    assert ex.reads == 0, "no page to read without a server"
    assert any("dev server" in r.message for r in caplog.records), caplog.text
    assert not any("browser driver" in r.message for r in caplog.records), caplog.text


@pytest.mark.asyncio
async def test_autorun_names_the_missing_driver_in_its_log(tmp_path, caplog):
    from vibe.autorun.policy import AutoRunPolicy

    ex = FakeBuildExecutor(url="http://127.0.0.1:5173/")
    policy = AutoRunPolicy(executor=ex, runtime=None, max_fix_iterations=3)
    with caplog.at_level(logging.WARNING, logger="vibe.autorun.policy"):
        await policy.maybe_run(_ctx(tmp_path, ex), ["App.tsx"])
    assert ex.reads == 1
    assert any("browser driver" in r.message for r in caplog.records), caplog.text
    assert not any("no dev server" in r.message for r in caplog.records), caplog.text


@pytest.mark.parametrize(
    ("status", "phrase"),
    [
        (UNREACHABLE, "not accepting connections"),
        (CAPTURE_FAILED, "could not be inspected"),
    ],
)
@pytest.mark.asyncio
async def test_autorun_puts_a_crashed_server_or_a_failed_capture_in_the_log(tmp_path, caplog, status, phrase):
    """Every cause reaches the log as itself; none of them reads as a missing driver."""
    from vibe.autorun.policy import AutoRunPolicy

    class Reasoned(FakeBuildExecutor):
        def __init__(self):
            super().__init__(url="http://127.0.0.1:5173/")
            self.console_reads = 0

        async def read_console(self, url, tail: int = 50, level: str = "error"):
            self.console_reads += 1
            return Capture(status, None)

        async def read_console_logs(self, url, tail: int = 50, level: str = "error"):
            raise AssertionError("autorun must prefer the reason-aware API")

    ex = Reasoned()
    policy = AutoRunPolicy(executor=ex, runtime=None, max_fix_iterations=3)
    with caplog.at_level(logging.WARNING, logger="vibe.autorun.policy"):
        await policy.maybe_run(_ctx(tmp_path, ex), ["App.tsx"])
    assert ex.console_reads == 1, "the reason-aware API is the one autorun asks"
    assert any(phrase in r.message for r in caplog.records), caplog.text
    assert not any("browser driver" in r.message for r in caplog.records), caplog.text


# --- the cause the executor itself reports (R3-T5) ---------------------------
#
# `read_console_logs`/`screenshot` still answer None for every cause, so the tools
# cannot tell them apart through the old API. The reason-aware methods answer
# *why*, and these tests pin the two causes the message split did not cover: a
# dev server that was started and then died (it has a URL, so it was reported as
# a missing driver -- the exact false diagnosis BE-09 is about), and a page that
# was reached but could not be inspected.


class ReasonExecutor(FakeExecutor):
    """Reports a cause, the way the real executor now does."""

    def __init__(self, *, status: str, value=None):
        super().__init__(url="http://127.0.0.1:5173/")
        self._status = status
        self._value = value

    async def read_console(self, url, tail: int = 50, level: str = "error"):
        self.console_calls += 1
        return Capture(self._status, self._value)

    async def capture_screenshot(self, url):
        self.screenshot_calls += 1
        return Capture(self._status, self._value)


@pytest.mark.asyncio
async def test_a_crashed_dev_server_is_not_reported_as_a_missing_driver(tmp_path):
    ex = ReasonExecutor(status=UNREACHABLE)
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert "not accepting connections" in r.content
    assert "run_dev_server" in r.content, "the fix is to start it again, not to install anything"
    assert "browser driver" not in r.content, "the driver is not the problem here"


@pytest.mark.asyncio
async def test_a_crashed_dev_server_is_not_reported_as_a_missing_driver_for_a_screenshot(tmp_path):
    ex = ReasonExecutor(status=UNREACHABLE)
    r = await _registry().execute("screenshot", {}, _ctx(tmp_path, ex))
    assert "not accepting connections" in r.content
    assert "browser driver" not in r.content


@pytest.mark.asyncio
async def test_a_failed_capture_names_itself_and_not_the_driver(tmp_path):
    ex = ReasonExecutor(status=CAPTURE_FAILED)
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert "could not be inspected" in r.content
    assert "browser driver" not in r.content
    assert "no dev server is running" not in r.content


@pytest.mark.asyncio
async def test_a_reason_aware_executor_still_returns_its_console_verbatim(tmp_path):
    ex = ReasonExecutor(status="ok", value="boom")
    r = await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))
    assert r.content == "boom"


@pytest.mark.asyncio
async def test_a_reason_aware_executor_still_returns_an_image(tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    ex = ReasonExecutor(status="ok", value=png)
    r = await _registry().execute("screenshot", {}, _ctx(tmp_path, ex))
    assert r.is_error is False
    assert len(r.attachments) == 1


@pytest.mark.asyncio
async def test_every_cause_has_its_own_message(tmp_path):
    """One message per cause, and none of them is another cause's message."""
    from vibe.tools.executor_tools import _UNAVAILABLE_WHY

    messages = set()
    for status in (NO_DEV_SERVER, NO_DRIVER, UNREACHABLE, CAPTURE_FAILED):
        ex = ReasonExecutor(status=status)
        console = (await _registry().execute("read_console_logs", {}, _ctx(tmp_path, ex))).content
        assert console.startswith("unavailable"), status
        assert status in _UNAVAILABLE_WHY, f"{status} has no message of its own"
        messages.add(console)
    assert len(messages) == 4, "two causes share one message again"


@pytest.mark.asyncio
async def test_no_dev_server_is_answered_without_asking_the_executor_to_read(tmp_path):
    """There is no page, so the executor is not even asked for one."""
    ex = FakeExecutor(url=None)
    capture = await capture_console(ex, None)
    assert capture.status == NO_DEV_SERVER
    assert ex.console_calls == 0


@pytest.mark.asyncio
async def test_an_executor_with_only_the_old_api_is_read_as_no_driver(tmp_path):
    """The old None still means what it always did, so callers migrate freely."""
    assert (await capture_console(FakeExecutor(url="http://x/", logs="hi"), "http://x/")).status == "ok"
    assert (await capture_console(FakeExecutor(url="http://x/", logs=None), "http://x/")).status == NO_DRIVER


# --- the real executor and the real driver ----------------------------------


@pytest.mark.asyncio
async def test_the_real_executor_says_no_dev_server_without_one(tmp_path):
    from vibe.executor.local import LocalSubprocessExecutor

    ex = LocalSubprocessExecutor(workspace=tmp_path)
    assert (await ex.read_console(None)).status == NO_DEV_SERVER
    assert (await ex.capture_screenshot(None)).status == NO_DEV_SERVER
    # The old view is unchanged: "nobody read this" is still None, not "".
    assert await ex.read_console_logs(None) is None
    assert await ex.screenshot(None) is None


@pytest.mark.asyncio
async def test_the_real_driver_says_no_driver_when_it_cannot_launch(monkeypatch):
    from vibe.executor.browser import BrowserDriver

    async def no_browser(self):
        return None

    monkeypatch.setattr(BrowserDriver, "_ensure", no_browser)
    driver = BrowserDriver()
    assert (await driver.read_console("http://127.0.0.1:1/")).status == NO_DRIVER
    assert (await driver.capture_screenshot("http://127.0.0.1:1/")).status == NO_DRIVER
    assert await driver.read_console_logs("http://127.0.0.1:1/") is None


@pytest.mark.asyncio
async def test_the_real_driver_says_unreachable_when_nothing_listens(monkeypatch):
    from vibe.executor.browser import BrowserDriver

    async def fake_browser(self):
        return object()

    async def never(self, url, attempts=40, delay=0.25):
        return False

    monkeypatch.setattr(BrowserDriver, "_ensure", fake_browser)
    monkeypatch.setattr(BrowserDriver, "_reachable", never)
    driver = BrowserDriver()
    assert (await driver.read_console("http://127.0.0.1:1/")).status == UNREACHABLE
    assert (await driver.capture_screenshot("http://127.0.0.1:1/")).status == UNREACHABLE


@pytest.mark.asyncio
async def test_a_page_that_raises_is_a_failed_capture_not_a_missing_driver(monkeypatch):
    from vibe.executor.browser import BrowserDriver

    class Boom:
        async def new_page(self):
            raise RuntimeError("boom")

    async def fake_browser(self):
        return Boom()

    async def reachable(self, url, attempts=40, delay=0.25):
        return True

    monkeypatch.setattr(BrowserDriver, "_ensure", fake_browser)
    monkeypatch.setattr(BrowserDriver, "_reachable", reachable)
    driver = BrowserDriver()
    assert (await driver.read_console("http://127.0.0.1:1/")).status == CAPTURE_FAILED
    assert (await driver.capture_screenshot("http://127.0.0.1:1/")).status == CAPTURE_FAILED
