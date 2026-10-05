# tests/test_errors.py
"""The error contract: one body shape, and a code a client can branch on.

The code is the frontend's only stable handle on a failure — the status is
transport and the message is prose that may change — so it gets its own tests
instead of being asserted incidentally through whichever route happened to
raise.
"""
from __future__ import annotations

from fastapi import HTTPException

from vibe.api.app import _handle_http_exception, _handle_unexpected
from vibe.api.errors import ApiError, ErrorCode, body


def _make_session(client) -> str:
    return client.post(
        "/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}}
    ).json()["id"]


# --- the contract itself ----------------------------------------------------

def test_body_is_the_single_error_shape():
    assert body(ErrorCode.NOT_FOUND, "gone") == {"error": {"code": "not_found", "message": "gone"}}


def test_api_error_takes_its_status_from_the_code():
    assert ApiError(ErrorCode.SESSION_NOT_FOUND, "x").status == 404
    assert ApiError(ErrorCode.NOT_FOUND, "x").status == 404
    assert ApiError(ErrorCode.RUN_IN_PROGRESS, "x").status == 409
    assert ApiError(ErrorCode.CONFLICT, "x").status == 409
    assert ApiError(ErrorCode.VALIDATION_FAILED, "x").status == 400
    assert ApiError(ErrorCode.PROVIDER_NOT_CONFIGURED, "x").status == 400
    assert ApiError(ErrorCode.INTERNAL, "x").status == 500


def test_api_error_status_can_be_overridden():
    assert ApiError(ErrorCode.NOT_FOUND, "x", status=410).status == 410


async def test_a_bare_http_exception_answers_in_the_shared_shape():
    """A route that forgot to migrate must not become the one endpoint the
    frontend cannot parse."""
    resp = await _handle_http_exception(None, HTTPException(404, "gone"))
    assert resp.status_code == 404
    assert resp.body == b'{"error":{"code":"not_found","message":"gone"}}'


async def test_an_unhandled_error_hides_its_message():
    resp = await _handle_unexpected(None, RuntimeError("leaked /etc/shadow"))
    assert resp.status_code == 500
    assert b"leaked" not in resp.body
    assert b'"code":"internal"' in resp.body


# --- through the app --------------------------------------------------------

def test_unknown_session_is_a_coded_404(client):
    resp = client.get("/sessions/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "session_not_found", "message": "session not found"}}


def test_unknown_approval_is_a_coded_404(client):
    resp = client.post("/approvals/nope/approve")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_invalid_after_seq_is_a_coded_400(client):
    sid = _make_session(client)
    resp = client.get(f"/sessions/{sid}/events?after_seq=not-a-number")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_failed"


def test_out_of_range_pagination_is_a_coded_422(client):
    sid = _make_session(client)
    resp = client.get(f"/sessions/{sid}/messages?limit=0")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"
    assert "limit" in resp.json()["error"]["message"]


def test_missing_provider_fields_are_a_coded_400(client):
    resp = client.post("/providers", json={"name": "x"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_failed"
