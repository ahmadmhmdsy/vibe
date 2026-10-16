# tests/test_install_offline.py
"""R5-T8: an offline machine must be told it is offline, in seconds.

pnpm used to be handed the install anyway: it waited out its own connect
timeout, retried, and then failed with output whose last lines name no cause the
user can act on. The executor now asks the registry first, remembers the answer,
and fails with one sentence that says what to do.

The network is never used here. The probe takes its connect function, its clock,
and its cache window as arguments, which is what makes "offline" a case a test
can drive instead of a machine state it has to hope for.
"""

import asyncio
import socket
import time

import pytest

from vibe import doctor
from vibe import registry as registry_module
from vibe.models import ToolResult
from vibe.registry import OFFLINE_MESSAGE, RegistryProbe


class FakeNetwork:
    """A network whose answers the test decides, and whose connects it counts."""

    def __init__(self, *answers: bool):
        self.answers = list(answers)
        self.calls = 0

    async def connect(self, host: str, port: int, timeout: float) -> bool:
        self.calls += 1
        return self.answers.pop(0) if self.answers else False


class Clock:
    def __init__(self, now: float = 0.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def _executor(tmp_path, probe):
    from vibe.executor.local import LocalSubprocessExecutor

    return LocalSubprocessExecutor(workspace=tmp_path, probe=probe)


def _offline_probe(network: FakeNetwork) -> RegistryProbe:
    """A probe that decides instantly, so the test measures the code, not DNS."""
    return RegistryProbe(connect=network.connect, retry_delay=0, timeout=0.01)


# --- the install fails fast, and says why -----------------------------------


@pytest.mark.asyncio
async def test_an_offline_install_fails_fast_without_running_pnpm(tmp_path):
    network = FakeNetwork(False, False)
    ex = _executor(tmp_path, _offline_probe(network))
    ran = []

    async def must_not_run(cmd):
        ran.append(cmd)
        raise AssertionError("pnpm must not be started when the registry is unreachable")

    ex._run = must_not_run
    started = time.perf_counter()
    result = await ex.install(["left-pad"])
    elapsed = time.perf_counter() - started

    assert result.is_error is True
    assert result.content == OFFLINE_MESSAGE
    assert ran == [], "the whole point is not to pay for the subprocess"
    assert elapsed < 1.0, f"an offline answer took {elapsed:.2f}s"


def test_the_offline_message_names_the_cause_and_the_action():
    assert "no network access" in OFFLINE_MESSAGE
    assert "npm registry" in OFFLINE_MESSAGE
    assert "connect once" in OFFLINE_MESSAGE
    assert "then retry" in OFFLINE_MESSAGE


@pytest.mark.asyncio
async def test_a_reachable_registry_installs_normally(tmp_path):
    network = FakeNetwork(True)
    ex = _executor(tmp_path, _offline_probe(network))
    calls = []

    async def fake_run(cmd):
        calls.append(cmd)
        return ToolResult("", cmd[0], "ok")

    ex._run = fake_run
    result = await ex.install(["left-pad"])

    assert result.is_error is False
    assert calls == [[ex._pnpm, "install", "left-pad"]]


# --- the answer is cached, so one session probes once ------------------------


@pytest.mark.asyncio
async def test_the_answer_is_cached_so_two_installs_probe_once(tmp_path):
    network = FakeNetwork(True)
    ex = _executor(tmp_path, _offline_probe(network))

    async def fake_run(cmd):
        return ToolResult("", cmd[0], "ok")

    ex._run = fake_run
    await ex.install([])
    await ex.install([])
    assert network.calls == 1


@pytest.mark.asyncio
async def test_a_failed_probe_is_retried_once_and_then_remembered():
    network = FakeNetwork(False, False)
    probe = _offline_probe(network)

    assert await probe.probe("registry.invalid", 443) is False
    assert network.calls == 2, "one retry: a single dropped SYN is not an offline machine"
    assert await probe.probe("registry.invalid", 443) is False
    assert network.calls == 2, "the second probe is inside the failure window"


@pytest.mark.asyncio
async def test_the_probe_recovers_when_the_network_comes_back():
    clock = Clock()
    network = FakeNetwork(False, False, True)
    probe = RegistryProbe(
        connect=network.connect,
        clock=clock,
        retry_delay=0,
        timeout=0.01,
        fail_ttl=30,
        ok_ttl=300,
    )

    assert await probe.probe("registry.invalid", 443) is False
    clock.now = 29.0
    assert await probe.probe("registry.invalid", 443) is False
    assert network.calls == 2, "still inside the failure window"
    clock.now = 31.0
    assert await probe.probe("registry.invalid", 443) is True
    assert network.calls == 3, "the failure expired, so the network is asked again"
    clock.now = 300.0
    assert await probe.probe("registry.invalid", 443) is True
    assert network.calls == 3, "a success is trusted for longer"


@pytest.mark.asyncio
async def test_a_hanging_connect_times_out_instead_of_hanging_the_install():
    async def hang(host, port, timeout):
        await asyncio.sleep(30)
        return True

    probe = RegistryProbe(connect=hang, retry_delay=0, timeout=0.05, attempts=1)
    started = time.perf_counter()
    assert await probe.probe("registry.invalid", 443) is False
    assert time.perf_counter() - started < 3.0


# --- the real connect, against ports the test owns ---------------------------


@pytest.mark.asyncio
async def test_the_real_connect_accepts_a_listener_and_refuses_a_closed_port():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        assert await RegistryProbe(attempts=1, timeout=1.0).probe("127.0.0.1", port) is True
    finally:
        listener.close()
    assert await RegistryProbe(attempts=1, timeout=1.0).probe("127.0.0.1", port) is False


def test_the_sync_probe_refuses_a_closed_port():
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()
    assert registry_module.reachable_sync("127.0.0.1", port) is False


def test_the_executor_shares_the_process_wide_probe(tmp_path):
    ex = _executor(tmp_path, None)
    assert ex._probe is registry_module.DEFAULT, "one answer per machine, not per session"


# --- the doctor says the same thing -----------------------------------------


def test_the_doctor_names_the_network_when_its_remedy_needs_a_download(monkeypatch):
    monkeypatch.setattr(doctor.registry, "reachable_sync", lambda *a, **k: False)
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    check = doctor._check_pnpm()
    assert "npm install -g pnpm" in check.remedy
    assert "registry is unreachable" in check.remedy


def test_the_doctor_names_the_network_for_uv_too(monkeypatch):
    monkeypatch.setattr(doctor.registry, "reachable_sync", lambda *a, **k: False)
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    assert "registry is unreachable" in doctor._check_uv().remedy


def test_the_doctor_stays_quiet_when_the_registry_answers(monkeypatch):
    monkeypatch.setattr(doctor.registry, "reachable_sync", lambda *a, **k: True)
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    assert doctor._check_pnpm().remedy == "install pnpm: npm install -g pnpm"
