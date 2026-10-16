# services/vibe/src/vibe/registry.py
"""Can this machine reach the npm registry? Ask once, cheaply, and remember.

An offline machine met the install step and paid for it: pnpm waited out its
own connect timeout, retried, and then failed with output whose last lines say
nothing about the network. The question worth answering first -- "can we reach
the registry at all?" -- is one TCP connect, and its answer holds for as long as
an install takes, so it is cached: a success for minutes, a failure for less,
because plugging the cable back in should not need a restart.

Nothing here downloads, authenticates, or parses; a completed TCP connect is the
whole test. A host that refuses connections is unreachable for our purposes
whether or not it would answer TLS.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

#: The host pnpm itself contacts first. Pinning it avoids a resolver round trip
#: of our own and keeps the probe to the one host an install cannot do without.
NPM_REGISTRY_HOST = "registry.npmjs.org"
NPM_REGISTRY_PORT = 443

#: What a user sees instead of a 120-second timeout and a truncated stack. It
#: names the one action that fixes an offline install, because "install failed"
#: on its own sends people to reinstall pnpm or hunt for a version conflict that
#: is not there.
OFFLINE_MESSAGE = (
    "no network access to the npm registry - connect once to install dependencies, then retry (nothing was downloaded)"
)

#: Short enough that an offline machine is told in seconds, long enough for a
#: slow resolver plus a slow SYN. Two attempts cost at most twice this.
DEFAULT_TIMEOUT_S = 2.5
RETRY_DELAY_S = 0.25
#: A success is stable, so it is trusted for the length of a session. A failure
#: is retested sooner: the user may be fixing the network right now.
OK_TTL_S = 300.0
FAIL_TTL_S = 30.0


async def _tcp_connect(host: str, port: int, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    except (TimeoutError, OSError) as e:
        logger.debug("registry probe: %s:%s unreachable (%s)", host, port, e)
        return False
    writer.close()
    # The peer may close first; the connect already succeeded either way.
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return True


def _tcp_connect_sync(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError as e:
        logger.debug("registry probe: %s:%s unreachable (%s)", host, port, e)
        return False


class RegistryProbe:
    """One cached answer to "can we reach the registry?" per (host, port).

    The connect function is injectable so a test can decide the answer without a
    network, and the clock is injectable so a test can watch the cache expire
    without sleeping.
    """

    def __init__(
        self,
        *,
        connect: Callable[[str, int, float], Awaitable[bool]] | None = None,
        connect_sync: Callable[[str, int, float], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = DEFAULT_TIMEOUT_S,
        ok_ttl: float = OK_TTL_S,
        fail_ttl: float = FAIL_TTL_S,
        retry_delay: float = RETRY_DELAY_S,
        attempts: int = 2,
    ):
        self._connect = connect or _tcp_connect
        self._connect_sync = connect_sync or _tcp_connect_sync
        self._clock = clock
        self._timeout = timeout
        self._ok_ttl = ok_ttl
        self._fail_ttl = fail_ttl
        self._retry_delay = retry_delay
        #: Two by default: one dropped SYN is not an offline machine, and being
        #: wrong here fails a working install with the wrong reason.
        self._attempts = max(1, attempts)
        self._cache: dict[tuple[str, int], tuple[bool, float]] = {}

    @property
    def timeout(self) -> float:
        return self._timeout

    def _cached(self, key: tuple[str, int]) -> bool | None:
        hit = self._cache.get(key)
        if hit is None:
            return None
        ok, at = hit
        ttl = self._ok_ttl if ok else self._fail_ttl
        return ok if (self._clock() - at) < ttl else None

    def _store(self, key: tuple[str, int], ok: bool) -> bool:
        self._cache[key] = (ok, self._clock())
        return ok

    async def _timed(self, attempt: Awaitable[bool]) -> bool:
        """Run one attempt under a hard ceiling.

        The real connect bounds itself, but the probe must not be hangable by a
        connect implementation that ignores its timeout, so the ceiling is
        enforced here too -- an install must never wait forever for a probe.
        """
        try:
            return await asyncio.wait_for(attempt, timeout=self._timeout + 1.0)
        except (TimeoutError, OSError):
            return False

    async def probe(self, host: str = NPM_REGISTRY_HOST, port: int = NPM_REGISTRY_PORT) -> bool:
        """True when the registry accepted a connection recently."""
        key = (host, port)
        cached = self._cached(key)
        if cached is not None:
            return cached
        ok = False
        for attempt in range(self._attempts):
            if attempt:
                await asyncio.sleep(self._retry_delay)
            ok = await self._timed(self._connect(host, port, self._timeout))
            if ok:
                break
        if not ok:
            logger.warning("registry %s:%s is unreachable; installs will fail fast", host, port)
        return self._store(key, ok)

    def probe_sync(self, host: str = NPM_REGISTRY_HOST, port: int = NPM_REGISTRY_PORT) -> bool:
        """The same question, for a synchronous caller such as the doctor."""
        key = (host, port)
        cached = self._cached(key)
        if cached is not None:
            return cached
        ok = False
        for attempt in range(self._attempts):
            if attempt:
                time.sleep(self._retry_delay)
            ok = self._connect_sync(host, port, self._timeout)
            if ok:
                break
        if not ok:
            logger.warning("registry %s:%s is unreachable", host, port)
        return self._store(key, ok)

    def forget(self) -> None:
        """Drop the cached answer, so the next call asks the network again."""
        self._cache.clear()


#: The probe every caller shares, so one install's answer is the next one's too.
DEFAULT = RegistryProbe()


async def reachable(host: str = NPM_REGISTRY_HOST, port: int = NPM_REGISTRY_PORT) -> bool:
    """True when the npm registry is reachable (cached; see RegistryProbe)."""
    return await DEFAULT.probe(host, port)


def reachable_sync(host: str = NPM_REGISTRY_HOST, port: int = NPM_REGISTRY_PORT) -> bool:
    """Reachable, for a synchronous caller."""
    return DEFAULT.probe_sync(host, port)


def forget() -> None:
    """Forget the cached answer -- a test seam, and a manual retry."""
    DEFAULT.forget()
