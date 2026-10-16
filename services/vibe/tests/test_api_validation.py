# tests/test_api_validation.py
"""R1-T4: probe 1 promoted -- unvalidated bodies must be 400s, not 500s (BE-01).

Every route used to take a raw dict and index it inside the handler, so bad
input failed there instead of at the edge: eight of these cases answered 500
"internal", one (provider_id: 1) was silently accepted because ModelRef does not
validate, and one wrote an empty file for an empty body. R2-T1 gives each route
a typed model (vibe/api/schemas.py) and maps FastAPI's RequestValidationError to
400 validation_failed. The strict xfail markers were removed with the fix;
these are its regression tests.
"""
import pytest
from fastapi.testclient import TestClient

BAD_SESSION_BODIES = [
    {},                                              # missing 'model'
    {"model": {}},                                   # missing provider_id/model_id
    {"model": {"provider_id": "openai"}},            # missing model_id
    {"model": ["openai", "gpt-4o"]},                 # not a mapping
    {"model": {"provider_id": 1, "model_id": "x"}},  # int where a string belongs
    ["openai", "gpt-4o"],                            # not an object at all
]


@pytest.fixture
def raw_client(app):
    """A client that returns a 5xx instead of re-raising, so it can be asserted."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("body", BAD_SESSION_BODIES)
def test_create_session_rejects_bad_bodies(raw_client, body):
    r = raw_client.post("/sessions", json=body)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_send_message_rejects_an_empty_body(raw_client, session_id):
    r = raw_client.post(f"/sessions/{session_id}/messages", json={})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_send_message_rejects_a_non_string_content(raw_client, session_id):
    r = raw_client.post(f"/sessions/{session_id}/messages", json={"content": 5})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_write_file_rejects_a_missing_body(raw_client, session_id):
    r = raw_client.put(f"/sessions/{session_id}/files/notes.txt", json={})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_write_file_rejects_a_non_string_content(raw_client, session_id):
    r = raw_client.put(f"/sessions/{session_id}/files/notes.txt", json={"content": 5})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"
