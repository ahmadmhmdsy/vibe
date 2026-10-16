# tests/test_logging_setup.py
"""R1-T4: probe 6 promoted -- the VIBE_HOST warning must be formattable (BE-07).

The lifespan calls

    logger.warning("VIBE_HOST=%s: bound beyond loopback; ...", " but ...", settings.host)

-- three positional arguments for one %s. logging defers that formatting error to
whichever handler formats the record, so the operator gets a "--- Logging error
---" traceback instead of the warning. R3-T3 fixed the call to one placeholder
and one argument; this capture handler formats the record and expects no failure.
"""
import logging
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from vibe.api.app import create_app
from vibe.config import Settings
from vibe.logging_setup import (
    DEFAULT_MAX_BYTES,
    configure_logging,
    log_startup_banner,
    redact_settings,
)


class CaptureHandler(logging.Handler):
    """Formats every record the way a real handler would, and keeps the failures."""

    def __init__(self):
        super().__init__()
        self.errors: list[str] = []
        self.formatted: list[str] = []

    def emit(self, record):
        try:
            self.formatted.append(record.getMessage())
        except Exception as e:
            self.errors.append(repr(e))


def test_remote_bind_warning_is_formattable(tmp_path):
    app = create_app(Settings(host="0.0.0.0", workspace_dir=tmp_path / "ws"))
    logger = logging.getLogger("vibe.api.app")
    capture = CaptureHandler()
    logger.addHandler(capture)
    try:
        with TestClient(app, raise_server_exceptions=False):
            pass
    finally:
        logger.removeHandler(capture)

    assert capture.errors == [], "formatting the warning raised"
    assert any("bound beyond loopback" in m for m in capture.formatted)


# --- R5-T5: the rotating log file and the startup banner -------------------
#
# The contract these pin: a bare configure_logging() keeps installing exactly
# one stderr handler (tests/test_logging.py owns that behaviour), while a call
# site that knows where the workspace is gets a rotating file as well, and no
# credential can reach it.


@pytest.fixture(autouse=True)
def _restore_vibe_logger():
    """Close the handlers configure_logging installed and put the logger back."""
    vibe_logger = logging.getLogger("vibe")
    before = list(vibe_logger.handlers)
    before_level = vibe_logger.level
    before_propagate = vibe_logger.propagate
    yield
    for handler in list(vibe_logger.handlers):
        if handler not in before:
            vibe_logger.removeHandler(handler)
            handler.close()
    vibe_logger.handlers = before
    vibe_logger.setLevel(before_level)
    vibe_logger.propagate = before_propagate


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_the_default_rotation_is_the_five_by_two_megabytes_the_plan_promises():
    assert DEFAULT_MAX_BYTES == 2 * 1024 * 1024


def test_a_bare_call_still_installs_only_the_stderr_handler():
    # Backwards compatibility is a contract, not a nicety: the audit tests
    # assert this, and a host that mounts the app itself expects no file.
    configure_logging("INFO")
    assert len(logging.getLogger("vibe").handlers) == 1


def test_the_environment_alone_can_turn_the_file_on(tmp_path, monkeypatch):
    target = tmp_path / "logs" / "vibe.log"
    monkeypatch.setenv("VIBE_LOG_FILE", str(target))
    # config.py resolves VIBE_LOG_FILE into Settings.log_file (guardrail L-6);
    # the end-to-end promise -- the environment alone turns the file on -- holds.
    configure_logging(settings=Settings.from_env())
    logging.getLogger("vibe.somewhere").info("hello from the env path")
    assert target.exists()
    assert "hello from the env path" in _lines(target)[-1]


def test_the_environment_can_turn_the_file_off(monkeypatch):
    monkeypatch.setenv("VIBE_LOG_FILE", "off")
    configure_logging(settings=Settings.from_env())
    assert len(logging.getLogger("vibe").handlers) == 1


def test_an_unset_vibe_log_file_still_writes_the_default_file(tmp_path, monkeypatch):
    # The default is a file under the workspace and only an explicit off value
    # may turn it off. An unset variable used to count as "off", which silently
    # contradicted the documented default: nobody got a log file unless they
    # named one. Proven end to end through the environment, not a hand-built
    # Settings, because that is the path python -m vibe takes.
    monkeypatch.delenv("VIBE_LOG_FILE", raising=False)
    monkeypatch.setenv("VIBE_WORKSPACE_DIR", str(tmp_path / "ws"))
    settings = Settings.from_env()
    assert settings.log_to_file is True
    assert settings.log_file == tmp_path / "ws" / "logs" / "vibe.log"

    configure_logging(settings=settings)
    logging.getLogger("vibe.somewhere").info("hello from the default path")
    assert settings.log_file.exists()
    assert "hello from the default path" in _lines(settings.log_file)[-1]


def test_settings_write_the_default_file_under_the_workspace(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws")
    configure_logging(settings=settings)
    logging.getLogger("vibe.executor.local").info("dev server started")

    target = tmp_path / "ws" / "logs" / "vibe.log"
    assert settings.log_file == target
    text = target.read_text(encoding="utf-8")
    assert "dev server started" in text
    # The file is an addition, never a replacement for the console.
    assert len(logging.getLogger("vibe").handlers) == 2
    # A bug report starts with the environment, so the banner is in the file.
    assert "vibe startup:" in text


def test_vibe_log_file_off_sets_the_setting_to_none():
    assert Settings(workspace_dir=".", log_to_file=False).log_file is None


def test_the_file_rotates_and_keeps_the_configured_number(tmp_path):
    target = tmp_path / "logs" / "vibe.log"
    configure_logging("INFO", log_file=target, max_bytes=400, backup_count=2)
    logger = logging.getLogger("vibe.rotation")
    for index in range(200):
        logger.info("rotation line %04d %s", index, "x" * 60)

    assert target.exists()
    assert target.with_name("vibe.log.1").exists()
    assert target.with_name("vibe.log.2").exists()
    assert not target.with_name("vibe.log.3").exists(), "backupCount must cap the set"


def test_a_log_directory_that_cannot_be_created_warns_but_does_not_stop_startup(tmp_path, capsys):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("i am a file", encoding="utf-8")

    configure_logging("INFO", log_file=blocker / "logs" / "vibe.log")

    captured = capsys.readouterr()
    assert "cannot write the log file" in captured.err
    # stderr only: the app still starts and still logs somewhere.
    assert len(logging.getLogger("vibe").handlers) == 1


SECRET = "sk-do-not-log-me-6f2b"


def test_a_settings_dump_never_writes_a_key_value(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    settings = Settings(
        workspace_dir=tmp_path / "ws",
        openai_api_key=SECRET,
        anthropic_api_key="sk-ant-also-secret",
    )
    configure_logging(settings=settings)
    logging.getLogger("vibe.startup").info("settings dump: %s", redact_settings(settings))

    text = (tmp_path / "ws" / "logs" / "vibe.log").read_text(encoding="utf-8")
    assert SECRET not in text
    assert "sk-ant-also-secret" not in text
    assert "***" in text, "the redaction marker must be visible in the dump"
    assert str(settings.workspace_dir) in text, "non-secret fields must survive"


def test_redaction_is_decided_by_field_name_not_by_a_hand_kept_list():
    @dataclass
    class Fake:
        username: str
        api_token: str
        password: str
        empty_key: str

    view = redact_settings(Fake("ahmad", "t0ken", "hunter2", ""))

    assert view["username"] == "ahmad"
    assert view["api_token"] == "***"
    assert view["password"] == "***"
    # An unset secret reads as None, not as "***": "configured but hidden" and
    # "not configured" must stay distinguishable in a bug report.
    assert view["empty_key"] is None


def test_the_banner_names_the_environment_it_started_in(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", port=7999, mode="prod", openai_api_key=SECRET)

    line = log_startup_banner(settings, probe=False)

    assert "vibe startup:" in line
    assert "version=" in line
    assert "python=" in line
    assert "mode=prod" in line
    assert "port=7999" in line
    assert str(settings.workspace_dir) in line
    assert SECRET not in line


def test_the_banner_reaches_the_file_on_startup(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", openai_api_key=SECRET)
    configure_logging(settings=settings, log_file=tmp_path / "logs" / "vibe.log")

    text = (tmp_path / "logs" / "vibe.log").read_text(encoding="utf-8")
    assert "vibe startup:" in text
    assert SECRET not in text


def test_the_probe_never_raises_on_a_machine_missing_the_tool(tmp_path, monkeypatch):
    # A missing node/pnpm must be a word in the banner, never an exception.
    # The version probe is cached per process, so clear it for this test.
    monkeypatch.setattr("vibe.logging_setup.shutil.which", lambda name: None)
    monkeypatch.setattr("vibe.logging_setup._VERSION_CACHE", {})
    settings = Settings(workspace_dir=tmp_path / "ws")
    line = log_startup_banner(settings, probe=True)
    assert "node=not found" in line
    assert "pnpm=not found" in line

