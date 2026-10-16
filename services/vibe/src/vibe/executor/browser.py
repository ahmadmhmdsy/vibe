# services/vibe/src/vibe/executor/browser.py
"""A real browser, so the agent can see the app it just built.

`read_console_logs` and `screenshot` were stubs returning None, and both the
autorun loop and the executor tools had to treat that as `no driver` rather
than `clean`. This module supplies the driver: Playwright, launched on first
use, one page per capture.

Every capture answers with a `Capture`: a value, or the reason there is none.
When Playwright or the browser binary is missing the reason is `no-driver`, so
a machine without a browser still runs -- it just cannot see the app. A server
that never came up and a capture that failed name themselves too, because they
are fixed differently (BE-09).
"""

from __future__ import annotations

import asyncio
import logging

from vibe.executor.base import CAPTURE_FAILED, NO_DRIVER, UNREACHABLE, Capture

logger = logging.getLogger(__name__)

# Playwright console message types carry no severity of their own, so map them.
# "all" keeps everything, "warning" keeps warnings and errors, "error" keeps
# only errors -- a healthy app prints warnings all day, and treating those as
# runtime errors would burn fix iterations on noise.
_SEVERITY = {"debug": 0, "log": 0, "info": 0, "warning": 1, "error": 2}
_MIN_SEVERITY = {"all": 0, "warning": 1, "error": 2}

# How long to let a page settle after load before reading the console. Runtime
# errors land after the load event, so reading immediately misses them.
_SETTLE_MS = 750


def _keep(message_type: str, level: str) -> bool:
    return _SEVERITY.get(message_type, 0) >= _MIN_SEVERITY.get(level, 2)


async def _close(page, url: str) -> None:
    """Close a capture page without letting cleanup replace the capture's answer.

    An exception raised in a `finally` block overrides the value being returned,
    so a page that died mid-capture would turn "capture-failed" into a traceback.
    """
    if page is None:
        return
    try:
        await page.close()
    except Exception as e:  # a page that is already gone cannot be closed
        logger.debug("could not close the capture page for %s: %s", url, e)


class BrowserDriver:
    """Owns the Playwright lifecycle for one executor.

    The browser is launched on first use, not at construction: starting it
    costs a process and a few hundred milliseconds, and most sessions never
    ask for a screenshot.
    """

    def __init__(self, *, headless: bool = True, timeout_ms: int = 10_000):
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None

    async def _ensure(self):
        """Launch the browser if it is not already up. None if unavailable."""
        if self._browser is not None:
            return self._browser
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("playwright is not installed; the agent cannot see the browser")
            return None
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self._headless)
        except Exception as e:
            # A missing browser binary is the common case on a fresh machine.
            logger.warning("browser unavailable: %s", e)
            self._playwright = None
            self._browser = None
            return None
        return self._browser

    async def _reachable(self, url: str, attempts: int = 40, delay: float = 0.25) -> bool:
        """Wait until the dev server accepts a connection.

        A freshly spawned Vite is not listening yet, and navigating before it
        is yields ERR_CONNECTION_REFUSED -- which is indistinguishable from a
        page that failed to load, so the capture would report nothing on a
        perfectly healthy app.
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        for _ in range(attempts):
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.0)
                writer.close()
                await writer.wait_closed()
                return True
            except OSError:
                await asyncio.sleep(delay)
        return False

    async def read_console(self, url: str, tail: int = 200, level: str = "error") -> Capture:
        """Console output from the page at `url`, or the reason there is none.

        The listeners are attached *before* navigating, so nothing printed
        during load is missed -- and so the page's own output is never confused
        with the dev server's stdout banner.

        A missing driver and a dev server that never came up are different
        problems with different fixes, so they are different answers here: the
        first means "install a browser", the second means "your server died".
        Collapsing them is what told users to install Playwright for a crashed
        Vite (BE-09).
        """
        browser = await self._ensure()
        if browser is None:
            return Capture(NO_DRIVER)
        if not await self._reachable(url):
            logger.warning("dev server at %s never became reachable; nothing was read", url)
            return Capture(UNREACHABLE)
        page = None
        records: list[str] = []
        try:
            # new_page is inside the guard: a browser whose context will not open
            # is a failed capture, not an unhandled exception in the tool layer.
            page = await browser.new_page()
            page.on("console", lambda m: records.append(m.text) if _keep(m.type, level) else None)
            page.on("pageerror", lambda e: records.append(f"pageerror: {e}"))
            await page.goto(url, wait_until="load", timeout=self._timeout_ms)
            await page.wait_for_timeout(_SETTLE_MS)
            return Capture(value="\n".join(records[-tail:]))
        except Exception as e:
            logger.warning("console capture failed for %s: %s", url, e)
            return Capture(CAPTURE_FAILED)
        finally:
            await _close(page, url)

    async def capture_screenshot(self, url: str) -> Capture:
        """A PNG of the page at `url`, or the reason there is none."""
        browser = await self._ensure()
        if browser is None:
            return Capture(NO_DRIVER)
        if not await self._reachable(url):
            logger.warning("dev server at %s never became reachable; no screenshot was taken", url)
            return Capture(UNREACHABLE)
        page = None
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="load", timeout=self._timeout_ms)
            await page.wait_for_timeout(_SETTLE_MS)
            return Capture(value=await page.screenshot(type="png"))
        except Exception as e:
            logger.warning("screenshot failed for %s: %s", url, e)
            return Capture(CAPTURE_FAILED)
        finally:
            await _close(page, url)

    # The None-returning forms stay, because "nobody read this" is a real state
    # that callers still branch on (the autorun check must not read None as
    # "clean"); they are now a lossy view over the reason above.

    async def read_console_logs(self, url: str, tail: int = 200, level: str = "error") -> str | None:
        """Console text, or None when no capture happened. See `read_console`."""
        capture = await self.read_console(url, tail=tail, level=level)
        return capture.value if capture.ok and isinstance(capture.value, str) else None

    async def screenshot(self, url: str) -> bytes | None:
        """PNG bytes, or None when no capture happened. See `capture_screenshot`."""
        capture = await self.capture_screenshot(url)
        return capture.value if capture.ok and isinstance(capture.value, bytes) else None

    async def close(self) -> None:
        """Shut the browser down. Safe to call more than once."""
        browser, self._browser = self._browser, None
        playwright, self._playwright = self._playwright, None
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                logger.debug("browser close failed", exc_info=True)
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                logger.debug("playwright stop failed", exc_info=True)
