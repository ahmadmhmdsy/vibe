# services/vibe/tests/test_doctor.py
"""The doctor is the first thing a stuck user runs, so its checks are tested
where they are cheap to be wrong: a probe that forgets its remedy, an exit code
that treats a warning as fatal, a port check that rubber-stamps a bound port.

Every environment probe is faked here; the real machine is exercised once by
running `python -m vibe doctor` for real (artifacts/hardening-r5-doctor.txt).
"""

from __future__ import annotations

import json
import platform
import socket
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from vibe import doctor
from vibe.config import Settings
from vibe.doctor import Check, exit_code, frontend_port, port_free, render, run_checks

EXPECTED_CHECKS = {
    "python",
    "node",
    "pnpm",
    "uv",
    "network",
    "chromium",
    "workspace",
    "providers-file",
    "providers-configured",
    "port-backend",
    "port-frontend",
}


def settings_for(tmp_path: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {"workspace_dir": tmp_path / "ws", "host": "127.0.0.1"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def by_name(checks: list[Check], name: str) -> Check:
    return next(check for check in checks if check.name == name)


def healthy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **overrides: object) -> Settings:
    """A machine where every probe succeeds, so a test can break exactly one."""
    monkeypatch.setattr(doctor, "_which", lambda name: f"C:/fake/{name}.exe")
    monkeypatch.setattr(doctor, "_command_version", lambda cmd: (24, 18, 0))
    monkeypatch.setattr(doctor, "chromium_dirs", lambda: [Path("C:/fake/ms-playwright/chromium-1243")])
    monkeypatch.setattr(doctor, "frontend_port", lambda repo_root=None: 5173)
    # The registry probe is faked so the doctor tests never touch the network.
    monkeypatch.setattr(doctor, "_network_reachable", lambda: True)
    return settings_for(tmp_path, **{"openai_api_key": "sk-test", **overrides})


# --- the happy path ---------------------------------------------------------


def test_python_check_reports_the_running_interpreter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check = by_name(run_checks(healthy(monkeypatch, tmp_path)), "python")
    assert check.ok is True
    assert check.detail == platform.python_version()


def test_all_green_exits_zero_with_no_warnings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    checks = run_checks(healthy(monkeypatch, tmp_path))
    assert [check.name for check in checks if not check.ok] == []
    assert exit_code(checks) == 0
    assert "all checks passed" in render(checks)


def test_run_checks_covers_every_documented_prerequisite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    names = {check.name for check in run_checks(healthy(monkeypatch, tmp_path))}
    assert names == EXPECTED_CHECKS
    assert names >= doctor.HARD_CHECKS


# --- missing tools name the exact command ------------------------------------


def test_missing_node_fails_and_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_which", lambda name: None if name == "node" else f"C:/fake/{name}.exe")
    checks = run_checks(settings)
    check = by_name(checks, "node")
    assert check.ok is False
    assert "https://nodejs.org" in check.remedy
    assert exit_code(checks) == 1


def test_too_old_node_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_command_version", lambda cmd: (18, 0, 0))
    check = by_name(run_checks(settings), "node")
    assert check.ok is False
    assert check.remedy


def test_missing_pnpm_names_the_install_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_which", lambda name: None if name == "pnpm" else f"C:/fake/{name}.exe")
    check = by_name(run_checks(settings), "pnpm")
    assert check.ok is False
    assert "npm install -g pnpm" in check.remedy


def test_missing_chromium_names_the_playwright_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "chromium_dirs", lambda: [])
    checks = run_checks(settings)
    check = by_name(checks, "chromium")
    assert check.ok is False
    assert "playwright install chromium" in check.remedy
    # A browser download is a feature gap, not a reason to refuse to start.
    assert check.name not in doctor.HARD_CHECKS
    assert exit_code(checks) == 0


def test_missing_uv_is_a_warning_not_a_blocker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_which", lambda name: None if name == "uv" else f"C:/fake/{name}.exe")
    checks = run_checks(settings)
    assert by_name(checks, "uv").ok is False
    assert exit_code(checks) == 0


def test_offline_network_is_a_warning_not_a_blocker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An offline machine is told the cause but still allowed to start."""
    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_network_reachable", lambda: False)
    checks = run_checks(settings)
    check = by_name(checks, "network")
    assert check.ok is False
    assert check.name not in doctor.HARD_CHECKS
    assert "pnpm install" in check.remedy
    assert exit_code(checks) == 0


def test_every_failing_check_offers_a_remedy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = settings_for(tmp_path)  # no env key either, so that check fails too
    monkeypatch.setattr(doctor, "_which", lambda name: None)
    monkeypatch.setattr(doctor, "_command_version", lambda cmd: None)
    monkeypatch.setattr(doctor, "chromium_dirs", lambda: [])
    # Network is up in this scenario; its own offline case is covered separately.
    monkeypatch.setattr(doctor, "_network_reachable", lambda: True)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    (settings.workspace_dir / "providers.json").write_text("{not json", encoding="utf-8")

    failing = [check for check in run_checks(settings) if not check.ok]
    assert [check.name for check in failing] == [
        "node",
        "pnpm",
        "uv",
        "chromium",
        "providers-file",
        "providers-configured",
    ]
    for check in failing:
        assert check.remedy.strip(), f"{check.name} fails without telling the user what to run"


# --- workspace ---------------------------------------------------------------


def test_workspace_is_created_and_leaves_no_probe_behind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    check = by_name(run_checks(settings), "workspace")
    assert check.ok is True
    assert settings.workspace_dir.is_dir()
    assert list(settings.workspace_dir.glob(".doctor-write-probe")) == []


def test_unusable_workspace_fails_with_a_way_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    settings = healthy(monkeypatch, tmp_path, workspace_dir=blocker / "ws")
    checks = run_checks(settings)
    check = by_name(checks, "workspace")
    assert check.ok is False
    assert "VIBE_WORKSPACE_DIR" in check.remedy
    # Everything else is green in this fixture, so this is what sets the code.
    assert exit_code(checks) == 1


# --- ports -------------------------------------------------------------------


def test_port_free_is_false_while_something_listens() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        assert port_free("127.0.0.1", listener.getsockname()[1]) is False


def test_port_free_follows_an_ipv6_host() -> None:
    """VIBE_HOST=::1 must not be reported as a busy port nothing is using."""
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as listener:
            listener.bind(("::1", 0))
            listener.listen(1)
            busy = listener.getsockname()[1]
            assert port_free("::1", busy) is False
    except OSError:
        pytest.skip("no IPv6 loopback on this machine")
    assert port_free("::1", busy) is True


def test_port_free_is_true_for_an_unused_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        free = listener.getsockname()[1]
    assert port_free("127.0.0.1", free) is True


def test_busy_backend_port_fails_and_says_how_to_move(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        caller = replace(settings, port=listener.getsockname()[1])
        check = by_name(run_checks(caller), "port-backend")
    assert check.ok is False
    assert "VIBE_PORT" in check.remedy


def test_busy_frontend_port_fails_and_names_the_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        busy = listener.getsockname()[1]
        monkeypatch.setattr(doctor, "frontend_port", lambda repo_root=None: busy)
        check = by_name(run_checks(settings), "port-frontend")
    assert check.ok is False
    assert "vite.config.ts" in check.remedy


def test_frontend_port_reads_vite_config(tmp_path: Path) -> None:
    app_dir = tmp_path / "apps" / "vibe"
    app_dir.mkdir(parents=True)
    (app_dir / "vite.config.ts").write_text("export default { server: { port: 5199 } };", encoding="utf-8")
    assert frontend_port(tmp_path) == 5199


def test_frontend_port_falls_back_to_vite_default(tmp_path: Path) -> None:
    (tmp_path / "apps" / "vibe").mkdir(parents=True)
    assert frontend_port(tmp_path) == doctor.VITE_DEFAULT_PORT


def test_repo_root_is_found_from_the_installed_package() -> None:
    root = doctor._repo_root()
    assert (root / "apps" / "vibe" / "vite.config.ts").exists()


# --- providers ---------------------------------------------------------------


def test_missing_providers_file_is_not_a_problem(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check = by_name(run_checks(healthy(monkeypatch, tmp_path)), "providers-file")
    assert check.ok is True
    assert "not created yet" in check.detail


def test_corrupt_providers_file_warns_without_blocking(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    (settings.workspace_dir / "providers.json").write_text("{not json", encoding="utf-8")
    checks = run_checks(settings)
    check = by_name(checks, "providers-file")
    assert check.ok is False
    assert "quarantine" in check.remedy
    assert check.name not in doctor.HARD_CHECKS
    assert exit_code(checks) == 0


def test_env_key_counts_as_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check = by_name(run_checks(healthy(monkeypatch, tmp_path)), "providers-configured")
    assert check.ok is True
    assert "openai" in check.detail


def test_custom_provider_counts_as_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path, openai_api_key=None)
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    (settings.workspace_dir / "providers.json").write_text(json.dumps({"p1": {"id": "p1"}}), encoding="utf-8")
    check = by_name(run_checks(settings), "providers-configured")
    assert check.ok is True
    assert "1 custom" in check.detail


def test_no_provider_at_all_is_a_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = healthy(monkeypatch, tmp_path, openai_api_key=None)
    checks = run_checks(settings)
    check = by_name(checks, "providers-configured")
    assert check.ok is False
    assert "OPENAI_API_KEY" in check.remedy
    # A missing key is the one thing every first-run user hits, and it must not
    # look like a broken install: warn, keep the exit code at zero.
    assert exit_code(checks) == 0


# --- exit code and rendering -------------------------------------------------


def test_exit_code_ignores_soft_failures() -> None:
    checks = [Check("python", True, "3.13.7"), Check("providers-configured", False, "no key", "set a key")]
    assert exit_code(checks) == 0


def test_exit_code_flags_hard_failures() -> None:
    assert exit_code([Check("pnpm", False, "missing", "npm install -g pnpm")]) == 1


def test_render_never_claims_success_beside_a_blocking_problem() -> None:
    """Regression: the failure-path run printed "1 blocking problem(s)" and
    "all checks passed" on adjacent lines, which is the one thing a preflight
    check must never do."""
    text = render([Check("python", True, "3.13.7"), Check("pnpm", False, "not found on PATH", "npm install -g pnpm")])
    assert "1 blocking problem(s): pnpm" in text
    assert "all checks passed" not in text
    assert "cannot start" in text


def test_render_says_a_warning_does_not_block() -> None:
    text = render(
        [Check("python", True, "3.13.7"), Check("chromium", False, "none found", "playwright install chromium")]
    )
    assert "1 warning(s): chromium" in text
    assert "no blocking problems" in text
    assert "all checks passed" not in text


def test_render_puts_the_remedy_under_its_own_check() -> None:
    text = render([Check("python", True, "3.13.7"), Check("pnpm", False, "not found on PATH", "npm install -g pnpm")])
    lines = text.splitlines()
    assert lines[0].startswith("PASS  python")
    assert lines[1].startswith("FAIL  pnpm")
    assert "npm install -g pnpm" in lines[2]
    assert "1 blocking problem" in text


# --- the CLI subcommand ------------------------------------------------------


def test_cli_doctor_prints_checks_and_returns_the_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from vibe import __main__ as cli

    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    assert cli.main(["doctor"]) == 0
    captured = capsys.readouterr().out
    assert "PASS  python" in captured
    assert "all checks passed" in captured


def test_cli_doctor_returns_one_when_a_hard_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from vibe import __main__ as cli

    settings = healthy(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor, "_which", lambda name: None if name == "pnpm" else f"C:/fake/{name}.exe")
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    assert cli.main(["doctor"]) == 1
    assert "npm install -g pnpm" in capsys.readouterr().out


# --- serving is still the default --------------------------------------------


def test_serve_is_the_default_and_gets_the_configured_host_and_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A bare "python -m vibe" must still serve, on the host and port Settings
    resolved rather than a constant compiled into __main__ (the old behaviour
    that silently ignored VIBE_HOST and VIBE_PORT)."""
    import uvicorn

    import vibe.api.app as api_app
    from vibe import __main__ as cli

    settings = healthy(monkeypatch, tmp_path)
    calls: dict[str, object] = {}
    # /admin/shutdown needs the Server object, so serve builds uvicorn.Server
    # itself instead of calling uvicorn.run - the host and port still come from
    # Settings, which is this test's actual subject.
    fake_app = SimpleNamespace(state=SimpleNamespace())

    class FakeServer:
        def __init__(self, config) -> None:
            calls["host"] = config.host
            calls["port"] = config.port

        def run(self) -> None:
            calls["ran"] = True

    def fake_create_app(resolved):
        calls["settings"] = resolved
        return fake_app

    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(api_app, "create_app", fake_create_app)
    monkeypatch.setattr(uvicorn, "Server", FakeServer)

    assert cli.main([]) == 0
    assert calls["settings"] is settings
    assert calls["host"] == settings.host
    assert calls["port"] == settings.port
    assert calls["ran"] is True
