# tests/test_settings_store.py
"""The workspace settings store, and the prompt precedence it feeds (BE-19).

The store is the layer that decides what "no override" means, so these tests pin
that meaning: a missing file, a corrupt file and a blank value all resolve to the
built-in default rather than to an empty instruction set. The last three tests
prove the two consumers - the chat turn and the auto-fix loop - read the prompt
when they run instead of snapshotting it at startup, which is what makes a save
in the GUI take effect without a restart.
"""

import json
import logging

from conftest import swap

from vibe.autorun.policy import AutoRunPolicy
from vibe.config import Settings
from vibe.container import Container
from vibe.models import AgentEvent
from vibe.prompts import DEFAULT_SYSTEM_PROMPT, system_prompt_for
from vibe.settings_store import SettingsStore, effective_override, resolve_prompt


class _EnvSettings:
    """Only the field resolve_prompt reads, so env precedence is provable without
    building a whole Settings and without touching the real environment."""

    def __init__(self, system_prompt: str = ""):
        self.system_prompt = system_prompt


# --- the store's own contract -----------------------------------------------


def test_missing_file_means_no_override(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.read_system_prompt() == ""
    assert system_prompt_for(store.read_system_prompt()) == DEFAULT_SYSTEM_PROMPT


def test_a_saved_prompt_round_trips(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.write_system_prompt("  You are terse.  ") == "You are terse."
    assert store.read_system_prompt() == "You are terse."
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {"system_prompt": "You are terse."}


def test_a_blank_prompt_clears_the_key_and_returns_the_default(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.write_system_prompt("You are terse.")
    assert store.write_system_prompt("   ") == ""
    assert store.read_system_prompt() == ""
    # The key is removed, not stored as "" - an empty string would be a real
    # override that leaves the agent unframed.
    assert "system_prompt" not in json.loads(path.read_text(encoding="utf-8"))
    assert system_prompt_for(store.read_system_prompt()) == DEFAULT_SYSTEM_PROMPT


def test_clearing_one_setting_keeps_the_others(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dark", "system_prompt": "x"}), encoding="utf-8")
    SettingsStore(path).write_system_prompt("")
    assert json.loads(path.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_a_corrupt_file_is_quarantined_and_reported_as_no_override(tmp_path, caplog):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    store = SettingsStore(path)
    with caplog.at_level(logging.WARNING, logger="vibe.settings_store"):
        assert store.read_system_prompt() == ""
    assert not path.exists(), "an unreadable file must be moved aside, not overwritten in place"
    quarantined = list(tmp_path.glob("settings.json.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "{not json"
    assert caplog.records, "quarantining a user's file has to be visible in the log"


def test_a_non_object_file_is_quarantined_too(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2]", encoding="utf-8")
    assert SettingsStore(path).read_system_prompt() == ""
    assert list(tmp_path.glob("settings.json.corrupt-*"))


def test_a_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.write_system_prompt("one")
    store.write_system_prompt("two")
    assert store.read_system_prompt() == "two"
    assert list(tmp_path.iterdir()) == [path], "a crashed write must not leave a *.tmp file behind"


# --- precedence: env > file > default ---------------------------------------


def test_the_environment_beats_the_file(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.write_system_prompt("from the file")
    assert resolve_prompt(_EnvSettings("from the env"), store) == ("from the env", "env")
    assert effective_override(_EnvSettings("from the env"), store) == "from the env"


def test_the_file_beats_the_default(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.write_system_prompt("from the file")
    assert resolve_prompt(_EnvSettings(""), store) == ("from the file", "file")


def test_a_blank_environment_value_is_not_an_override(tmp_path):
    # Settings.system_prompt defaults to "", so "set but empty" must not count as
    # configured - otherwise the GUI could never win and the source line would
    # always claim the environment.
    store = SettingsStore(tmp_path / "settings.json")
    store.write_system_prompt("from the file")
    assert resolve_prompt(_EnvSettings("   "), store) == ("from the file", "file")


def test_the_default_when_neither_layer_says_anything(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    override, source = resolve_prompt(_EnvSettings(""), store)
    assert (override, source) == ("", "default")
    assert system_prompt_for(override) == DEFAULT_SYSTEM_PROMPT


# --- the container's wiring -------------------------------------------------


def test_the_container_builds_the_store_inside_the_workspace(tmp_path):
    container = Container.build(Settings(workspace_dir=tmp_path / "ws", port=8000))
    assert container.settings_store.path == tmp_path / "ws" / "settings.json"


def test_the_container_accepts_an_overridden_store(tmp_path):
    mine = SettingsStore(tmp_path / "elsewhere.json")
    container = Container.build(Settings(workspace_dir=tmp_path / "ws", port=8000), settings_store=mine)
    assert container.settings_store is mine


# --- the consumers read it when they run, not at startup --------------------


class _CapturingRuntime:
    """Records the system prompt handed to the model on every run."""

    def __init__(self):
        self.prompts: list[str] = []

    async def run(self, input, ctx):
        self.prompts.append(input.system)
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


def test_a_saved_prompt_reaches_the_next_turn_without_a_restart(client, app, session_id):
    runtime = _CapturingRuntime()
    swap(app, runtime=runtime)

    body = client.patch("/settings", json={"system_prompt": "Speak in haiku."}).json()["system_prompt"]
    assert client.post(f"/sessions/{session_id}/messages", json={"content": "hi"}).status_code == 200

    # Read per turn: nothing was restarted and no container was rebuilt between
    # the PATCH and the send.
    assert runtime.prompts == [body["effective"]]
    assert runtime.prompts[0] == (body["configured"].strip() or "Speak in haiku.")


def test_the_fix_loop_resolves_a_callable_prompt_each_time():
    """The auto-fix loop must not freeze the prompt at construction: a prompt
    saved while the app runs has to reach the next fix turn."""
    saved = {"value": "first"}
    policy = AutoRunPolicy(executor=None, runtime=None, system_prompt=lambda: saved["value"])
    assert policy._prompt_override() == "first"
    saved["value"] = "second"
    assert policy._prompt_override() == "second"

    # A plain string is still a fixed prompt, and no prompt stays no prompt.
    assert AutoRunPolicy(executor=None, runtime=None, system_prompt="fixed")._prompt_override() == "fixed"
    assert AutoRunPolicy(executor=None, runtime=None)._prompt_override() is None


def test_the_container_hands_the_fix_loop_a_live_resolver(tmp_path):
    """The wiring the test above relies on: one policy, asked twice, sees a save."""
    settings = Settings(workspace_dir=tmp_path / "ws", port=8000)
    container = Container.build(settings)
    container.settings_store.write_system_prompt("from the file")
    container.get_autorun("s1", tmp_path / "ws" / "s1")

    policy = container.get_autorun("s1", tmp_path / "ws" / "s1")
    assert policy._prompt_override() == "from the file"
    container.settings_store.write_system_prompt("changed mid-flight")
    assert policy._prompt_override() == "changed mid-flight"
