# tests/test_api_gaps.py
"""R3-T6 (BE-10): small contract gaps in the sessions routes.

Also the two questions the plan's bullet list left open: the Settings panel's
"Clear stored key" call (does an empty apiKey really clear the key?) and the
GUI system-prompt field's read and write contract.
"""

import json
import logging
from dataclasses import MISSING, fields

from conftest import swap

from vibe.container import Container
from vibe.usage.tracker import UsageTracker


class RaisingRuntime:
    """An async generator that fails before producing a turn."""

    def __init__(self, exc):
        self._exc = exc

    async def run(self, input, ctx):
        raise self._exc
        yield  # pragma: no cover - makes this an async generator


def _new_sid(client):
    return client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}).json()["id"]


# --- the dead usage branch --------------------------------------------------


def test_the_container_cannot_be_built_without_a_usage_tracker():
    """Why the route's `if usage is None` was dead: the field has no default and
    Container.build always constructs a UsageTracker, so the 404 branch could
    never run and was never tested. Deleting it is only safe because of this."""
    usage = next(f for f in fields(Container) if f.name == "usage")
    assert usage.default is MISSING and usage.default_factory is MISSING


def test_usage_endpoint_answers_even_with_no_usage_recorded(client, app):
    assert isinstance(app.state.container.usage, UsageTracker)
    sid = _new_sid(client)
    resp = client.get(f"/sessions/{sid}/usage")
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_tokens"] == 0
    assert resp.json()["by_model"] == []


# --- the single-session shape ----------------------------------------------


def test_get_session_has_the_same_shape_as_the_list_row(client):
    sid = _new_sid(client)
    one = client.get(f"/sessions/{sid}").json()
    listed = client.get("/sessions").json()[0]
    assert set(one) == set(listed), "a client must not need two types for one session"
    assert one["created_at"] == listed["created_at"]
    assert one["updated_at"] == listed["updated_at"]
    assert one["created_at"] and one["updated_at"]


def test_rename_moves_updated_at_but_not_created_at(client):
    sid = _new_sid(client)
    before = client.get(f"/sessions/{sid}").json()
    client.patch(f"/sessions/{sid}", json={"title": "renamed"})
    after = client.get(f"/sessions/{sid}").json()
    assert after["title"] == "renamed"
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] >= before["updated_at"]


# --- the read-only settings view (BE-19) ------------------------------------


def test_settings_reports_the_effective_system_prompt(client):
    body = client.get("/settings").json()["system_prompt"]
    assert set(body) == {"configured", "effective", "default", "source"}
    # The effective prompt is never empty - an unset override must not leave the
    # agent unframed - and it is exactly the override when one is configured.
    assert body["effective"].strip()
    assert body["effective"] == (body["configured"].strip() or body["default"])
    # `source` names the winning layer: env, the workspace file, or the built-in
    # default. "configured" is what the environment value used to be called.
    assert body["source"] == ("env" if body["configured"].strip() else "default")


# --- raw exception text on the client --------------------------------------


def test_an_internal_error_sends_a_generic_message_with_a_correlation_id(client, app, caplog):
    swap(app, runtime=RaisingRuntime(RuntimeError("leaked /etc/shadow and sk-secret-value")))
    sid = _new_sid(client)
    with caplog.at_level(logging.ERROR, logger="vibe.api.routes.chat"):
        resp = client.post(f"/sessions/{sid}/messages", json={"content": "hi"})

    assert resp.status_code == 500, resp.text
    error = resp.json()["error"]
    assert error["code"] == "internal"
    assert "leaked" not in resp.text and "sk-secret" not in resp.text
    assert "error id " in error["message"]
    eid = error["message"].split("error id ", 1)[1].rstrip(")")
    assert eid

    # the detail is logged, together with the id the user can quote
    assert any(eid in r.getMessage() and "leaked" in r.getMessage() for r in caplog.records), caplog.text


def test_the_error_turn_recorded_for_the_user_carries_the_generic_message(client, app):
    swap(app, runtime=RaisingRuntime(RuntimeError("leaked /etc/shadow")))
    sid = _new_sid(client)
    client.post(f"/sessions/{sid}/messages", json={"content": "hi"})
    history = client.get(f"/sessions/{sid}/messages").json()
    assistant = [m for m in history if m["role"] == "assistant"]
    assert assistant, "a failed turn must still be explained in the transcript"
    assert "leaked" not in assistant[-1]["content"]
    assert "error id " in assistant[-1]["content"]


def test_a_validation_error_keeps_its_actionable_message(client, app):
    swap(app, runtime=RaisingRuntime(ValueError("model is not configured for this session")))
    sid = _new_sid(client)
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "hi"})
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "validation_failed"
    assert resp.json()["error"]["message"] == "model is not configured for this session"


def test_provider_not_configured_keeps_its_explicit_message(client, app):
    """The one failure the UI can tell the user how to resolve keeps its text."""
    from vibe.providers.registry import ProviderNotConfigured

    swap(
        app,
        runtime=RaisingRuntime(
            ProviderNotConfigured("OPENAI_API_KEY is not configured. Set it in .env or use a different provider.")
        ),
    )
    sid = _new_sid(client)
    resp = client.post(f"/sessions/{sid}/messages", json={"content": "hi"})
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "provider_not_configured"
    assert "OPENAI_API_KEY" in resp.json()["error"]["message"]


# --- 6a: the Settings panel's "Clear stored key" ---------------------------


def test_clear_stored_key_with_an_empty_api_key(client, store_path):
    """The Settings panel sends PATCH {apiKey: ""}; verify it really clears.

    R2 measured POST/PATCH /providers with apiKey:"" returning
    key_configured=false. This pins the whole path: create with a key, clear it,
    read it back, and confirm the key is gone from the file on disk too -- not
    just from the response.
    """
    created = client.post(
        "/providers",
        json={
            "name": "Local",
            "baseUrl": "http://x/v1",
            "apiKey": "sk-live",
            "models": [{"id": "m1", "name": "M1"}],
        },
    ).json()
    assert created["key_configured"] is True

    resp = client.patch(f"/providers/{created['id']}", json={"apiKey": ""})
    assert resp.status_code == 200, resp.text
    assert resp.json()["key_configured"] is False

    listed = [p for p in client.get("/providers").json() if p["id"] == created["id"]]
    assert listed and listed[0]["key_configured"] is False

    on_disk = json.loads(store_path.read_text(encoding="utf-8"))
    assert on_disk[created["id"]]["api_key"] == "", "the key must be gone from the store, not just hidden"
    assert "sk-live" not in store_path.read_text(encoding="utf-8")


# --- 6b: the GUI system-prompt field's surface ------------------------------
#
# This file originally documented a gap: no route exposed the prompt, so a GUI
# field had nothing to read. GET /settings closed the read half; PATCH /settings
# closes the write half (BE-19) by persisting to the workspace's settings.json -
# the persistence story the read-only version was waiting for. The environment
# still beats the file, so `source` is how a client knows whether a write can
# take effect at all.


def test_put_settings_stays_method_not_allowed(client):
    """PATCH is the only writer: PUT would imply whole-object replacement, and
    this app does not own every field of that object."""
    assert client.get("/settings").status_code == 200
    assert client.put("/settings", json={"system_prompt": "x"}).status_code == 405


def test_patch_settings_saves_a_prompt_and_clears_it(client):
    created = client.patch("/settings", json={"system_prompt": "You are terse."})
    assert created.status_code == 200, created.text
    body = created.json()["system_prompt"]
    assert set(body) == {"configured", "effective", "default", "source"}
    if body["configured"].strip():
        # The environment is the operator override and keeps winning, which is
        # exactly what `source` tells the GUI.
        assert body["source"] == "env"
        assert body["effective"] == body["configured"].strip()
    else:
        assert body["source"] == "file"
        assert body["effective"] == "You are terse."

    cleared = client.patch("/settings", json={"system_prompt": ""})
    cleared_body = cleared.json()["system_prompt"]
    assert cleared_body["source"] == ("env" if cleared_body["configured"].strip() else "default")
    assert cleared_body["effective"] == (cleared_body["configured"].strip() or cleared_body["default"])


def test_patch_settings_rejects_a_bad_body_with_a_400(client):
    # A wrong type and a missing key are both validation failures: the second
    # matters because a missing key must not silently clear the saved prompt.
    for payload in ({"system_prompt": 5}, {}, {"system_prompt": "x" * 20_001}):
        resp = client.patch("/settings", json=payload)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "validation_failed", resp.text
