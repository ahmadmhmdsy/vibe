# tests/test_static_serving.py
"""Production single-port mode: one process serves the API and the SPA (R5-T3)."""

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from vibe.api.app import create_app
from vibe.api.static import mount_spa
from vibe.config import Settings


def make_dist(tmp_path: Path) -> Path:
    """A stand-in for what "pnpm run build" emits."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root>shell</div>", encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def client_for(app, *, host: str = "127.0.0.1"):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(host, 51000)),
        base_url="http://localhost",
    )


def test_a_missing_build_fails_loudly_instead_of_serving_a_blank_page(tmp_path):
    with pytest.raises(RuntimeError, match="pnpm run build"):
        mount_spa(FastAPI(), tmp_path / "never-built")


@pytest.mark.asyncio
async def test_shell_asset_deep_link_and_api_404(tmp_path):
    app = FastAPI()
    mount_spa(app, make_dist(tmp_path))
    async with client_for(app) as client:
        shell = await client.get("/")
        assert shell.status_code == 200
        assert "shell" in shell.text
        # index.html names hashed assets, so it must never be cached blindly.
        assert shell.headers["cache-control"] == "no-cache"

        asset = await client.get("/assets/app-abc123.js")
        assert asset.status_code == 200
        assert "console.log(1)" in asset.text
        assert "immutable" in asset.headers["cache-control"]

        # A client route has no file behind it; it must still return the shell,
        # or refreshing a deep link looks like the data vanished.
        deep = await client.get("/sessions/abc123")
        assert deep.status_code == 200
        assert "shell" in deep.text

        # A missing asset is a real 404: a mount does not fall through to the
        # shell, so a broken build cannot masquerade as a working page.
        assert (await client.get("/assets/gone.js")).status_code == 404


@pytest.mark.asyncio
async def test_api_namespace_is_never_answered_with_the_shell(tmp_path):
    app = FastAPI()
    mount_spa(app, make_dist(tmp_path))
    async with client_for(app) as client:
        resp = await client.get("/api/nonsense")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"
        assert "shell" not in resp.text


@pytest.mark.asyncio
async def test_a_traversal_path_cannot_read_outside_the_build(tmp_path):
    dist = make_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me", encoding="utf-8")
    app = FastAPI()
    mount_spa(app, dist)
    async with client_for(app) as client:
        # %2e%2e%2f survives client-side normalisation and reaches the route.
        resp = await client.get("/%2e%2e%2fsecret.txt")
        assert resp.status_code == 200
        assert "do not serve me" not in resp.text
        assert "shell" in resp.text


@pytest.mark.asyncio
async def test_prod_app_serves_health_and_shell_on_one_origin(tmp_path):
    settings = Settings(workspace_dir=tmp_path / "ws", mode="prod", static_dir=make_dist(tmp_path))
    app = create_app(settings)
    async with client_for(app) as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        shell = await client.get("/")
        assert shell.status_code == 200
        assert "shell" in shell.text
        bogus = await client.get("/api/nonsense")
        assert bogus.status_code == 404
        assert bogus.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_dev_mode_mounts_nothing(tmp_path):
    """Dev keeps Vite as the only thing serving "/", by design."""
    settings = Settings(workspace_dir=tmp_path / "ws", mode="dev")
    app = create_app(settings)
    async with client_for(app) as client:
        assert (await client.get("/")).status_code == 404


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="VIBE_MODE"):
        Settings(mode="production")
