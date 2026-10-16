# services/vibe/tests/test_auth.py
"""Loopback auth: who gets in, who is refused, and why there are two controls.

The app is local-first, so the whole auth story is "did this request come from
this machine". These tests pin the three properties that matter:

  * a local peer is accepted, and gets a Principal it can be identified by;
  * a non-local peer is refused with a machine-readable code, not a stack trace;
  * the Origin check is a *second* control, because loopback auth cannot catch
    a CSRF request that arrives from 127.0.0.1.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from vibe.auth import LoopbackAuthenticator, Principal
from vibe.container import Container


def _request(client_host, method: str = "GET") -> Request:
    """A Request with an explicit peer address.

    client_host=None reproduces an in-process ASGI call, where Starlette leaves
    request.client unset.
    """
    scope = {"type": "http", "method": method, "path": "/", "headers": []}
    if client_host is not None:
        scope["client"] = (client_host, 43210)
    return Request(scope)


# --- the authenticator itself -------------------------------------------------

@pytest.mark.asyncio
async def test_a_loopback_peer_is_accepted():
    principal = await LoopbackAuthenticator().authenticate(_request("127.0.0.1"))
    assert principal == Principal(id="local", name="local")


@pytest.mark.asyncio
async def test_a_non_loopback_peer_is_refused():
    assert await LoopbackAuthenticator().authenticate(_request("203.0.113.10")) is None


@pytest.mark.asyncio
async def test_an_in_process_call_counts_as_local():
    """request.client is None when no socket was involved.

    An internal caller is not a network peer, so refusing it would break every
    in-process use of the app.
    """
    assert await LoopbackAuthenticator().authenticate(_request(None)) is not None


@pytest.mark.asyncio
async def test_the_testclient_peer_counts_as_local():
    """The suite runs through TestClient, which reports host "testclient".

    If this were not in the allowlist, every existing test would start failing
    with a 401 the moment the routers were mounted behind the authenticator.
    """
    assert await LoopbackAuthenticator().authenticate(_request("testclient")) is not None


# --- over the real app --------------------------------------------------------

def test_a_local_request_succeeds(client):
    r = client.get("/sessions")
    assert r.status_code == 200


def test_a_non_loopback_peer_is_refused_with_a_code(app):
    remote = TestClient(app, client=("203.0.113.10", 5555))
    r = remote.get("/sessions")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_health_stays_open(client):
    """/health is a direct route, not part of a router, so it needs no principal.

    It is how a load balancer and a curious browser check liveness without
    being able to authenticate.
    """
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- the Origin guard: a second, independent control --------------------------

def test_a_foreign_origin_is_refused_on_a_state_changing_request(client):
    r = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}},
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


def test_an_allowed_origin_is_accepted(client):
    r = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}},
                    headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 201


def test_a_missing_origin_is_allowed(client):
    """Non-browser clients send no Origin, and loopback auth has already gated them."""
    r = client.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})
    assert r.status_code == 201


def test_the_origin_guard_does_not_apply_to_reads(client):
    """A GET cannot be a CSRF vector, so the guard leaves it alone."""
    r = client.get("/sessions", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200


# --- the Origin guard: same-origin is trusted without an allowlist entry -------
#
# In prod the app serves the SPA itself, so the page's Origin is the server's
# own host:port and no allowlist entry could name it without knowing the port
# in advance. A same-origin request is therefore accepted even though it is not
# listed. TestClient sends "Host: testserver", so every case here states Host.

_SESSION_BODY = {"model": {"provider_id": "openai", "model_id": "gpt-4o"}}


def _post_from(client, origin: str, host: str):
    return client.post("/sessions", json=_SESSION_BODY, headers={"Origin": origin, "Host": host})


def test_a_same_origin_request_on_an_explicit_port_is_accepted(client):
    """The prod-mode case: the app serves the SPA on its own 127.0.0.1:7322.

    The Origin here is deliberately not in the allowlist (the default list only
    names localhost:5173 and 127.0.0.1:5173), so this passes only because the
    stated Origin is same-origin with the request's own Host.
    """
    r = _post_from(client, "http://127.0.0.1:7322", "127.0.0.1:7322")
    assert r.status_code == 201


def test_a_different_port_on_the_same_host_is_refused(client):
    """A page on another local port is a different origin, not ours."""
    r = _post_from(client, "http://127.0.0.1:7321", "127.0.0.1:7322")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


def test_a_default_port_is_normalized_against_an_explicit_one(client):
    """http://127.0.0.1 and 127.0.0.1:80 are the same origin."""
    r = _post_from(client, "http://127.0.0.1", "127.0.0.1:80")
    assert r.status_code == 201


def test_a_scheme_mismatch_is_refused(client):
    """https://127.0.0.1:7322 is a different origin from the http one."""
    r = _post_from(client, "https://127.0.0.1:7322", "127.0.0.1:7322")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


def test_localhost_is_not_treated_as_127_0_0_1(client):
    """The two names reach the same machine but are distinct origins."""
    r = _post_from(client, "http://localhost:7322", "127.0.0.1:7322")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_origin"


# --- the seam -----------------------------------------------------------------

def test_a_swapped_authenticator_is_the_one_that_runs(app):
    """The container is the only place the authenticator is chosen.

    A future TokenAuthenticator is verified by exactly this test: swap the
    seam, watch the answer change.
    """
    class RefuseEverything:
        async def authenticate(self, request):
            return None

    from dataclasses import replace
    app.state.container = replace(app.state.container, authenticator=RefuseEverything())
    r = TestClient(app).get("/sessions")
    assert r.status_code == 401


def test_an_unknown_auth_mode_raises_rather_than_downgrading(tmp_path):
    """A typo must not silently become the permissive option."""
    from vibe.config import Settings
    with pytest.raises(ValueError, match="VIBE_AUTH_MODE"):
        Container.build(Settings(workspace_dir=tmp_path / "ws", auth_mode="token"))
