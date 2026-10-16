# services/vibe/tests/test_logging.py
"""Tests for vibe.logging_setup (audit H5).

The backend had no logging at all before this: a failure inside the
idle-dev-server reaper or a streaming run was swallowed. configure_logging
is now the single place that decides where records go, so these tests pin
its contract - level resolution, idempotency, and the propagation flag that
stops a host application from printing every line twice.
"""
from __future__ import annotations

import logging

import pytest

from vibe.config import Settings
from vibe.logging_setup import DEFAULT_LEVEL, configure_logging


@pytest.fixture(autouse=True)
def _restore_vibe_logger():
    """Put the vibe logger back exactly as we found it."""
    vibe_logger = logging.getLogger("vibe")
    before_handlers = list(vibe_logger.handlers)
    before_level = vibe_logger.level
    before_propagate = vibe_logger.propagate
    yield
    vibe_logger.handlers = before_handlers
    vibe_logger.setLevel(before_level)
    vibe_logger.propagate = before_propagate


def test_installs_exactly_one_handler_and_stops_propagation():
    configure_logging("DEBUG")
    vibe_logger = logging.getLogger("vibe")
    assert len(vibe_logger.handlers) == 1
    assert vibe_logger.level == logging.DEBUG
    # Ours owns the records now; otherwise a configured root logger would
    # duplicate every line.
    assert vibe_logger.propagate is False


def test_is_idempotent():
    configure_logging("INFO")
    configure_logging("INFO")
    configure_logging("INFO")
    assert len(logging.getLogger("vibe").handlers) == 1


def test_accepts_an_int_level():
    assert configure_logging(logging.WARNING) == logging.WARNING
    assert logging.getLogger("vibe").level == logging.WARNING


def test_unknown_level_name_falls_back_to_the_default():
    # A typo in VIBE_LOG_LEVEL must not stop the server from booting.
    assert configure_logging("NOT-A-LEVEL") == logging.getLevelName(DEFAULT_LEVEL)


def test_level_name_is_case_insensitive():
    assert configure_logging("debug") == logging.DEBUG


def test_level_comes_from_the_environment(monkeypatch):
    # The environment still sets the level, but it reaches logging through
    # Settings: config.py is the only module that reads it (guardrail L-6).
    monkeypatch.setenv("VIBE_LOG_LEVEL", "debug")
    assert configure_logging(settings=Settings.from_env()) == logging.DEBUG


def test_blank_environment_level_falls_back(monkeypatch):
    # An empty VIBE_LOG_LEVEL must not be read as level 0 ("NOTSET").
    monkeypatch.setenv("VIBE_LOG_LEVEL", "")
    assert configure_logging(settings=Settings.from_env()) == logging.getLevelName(DEFAULT_LEVEL)


def test_records_from_child_loggers_reach_the_handler():
    configure_logging("INFO")
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    logging.getLogger("vibe").addHandler(_Capture())
    logging.getLogger("vibe.executor.local").info("dev server started on port %s", 1234)

    assert "dev server started on port 1234" in captured


def test_child_logger_level_is_governed_by_the_parent():
    configure_logging("WARNING")
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    logging.getLogger("vibe").addHandler(_Capture())
    logging.getLogger("vibe.lifecycle").info("should be filtered")

    assert captured == []
