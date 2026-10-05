# services/vibe/tests/test_config.py
from vibe.config import DEFAULT_CORS_ORIGINS, Settings


def test_default_cors_origins():
    s = Settings()
    assert s.cors_origins == DEFAULT_CORS_ORIGINS.split(",")


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("VIBE_CORS_ORIGINS", "http://localhost:5174, http://127.0.0.1:5174")
    s = Settings.from_env()
    assert s.cors_origins == ["http://localhost:5174", "http://127.0.0.1:5174"]


def test_cors_middleware_allows_configured_origin(client, app):
    origin = app.state.container.settings.cors_origins[0]
    resp = client.options(
        "/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin


def test_cors_middleware_rejects_unknown_origin(client, app):
    resp = client.options(
        "/sessions",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Disallowed origin: no ACAO header (browser blocks the read).
    assert "access-control-allow-origin" not in resp.headers
