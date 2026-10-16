"""Probe 2: custom-provider store robustness (read-only, temp dirs only).

Claims under test:
  C1  a custom model dict missing "id" makes GET /catalog answer 500
  C2  a corrupt providers.json makes GET /providers answer 500
  C3  POST /providers accepts a model with no "id" (invalid state is creatable)
  C4  the API can clear an api key (only the UI cannot)
"""
from __future__ import annotations

import json
import pathlib
import tempfile

from fastapi.testclient import TestClient

from vibe.api.app import create_app
from vibe.config import Settings


def main() -> int:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root = pathlib.Path(tmp.name)
    settings = Settings(workspace_dir=root)
    app = create_app(settings)
    results: list[str] = []

    with TestClient(app, raise_server_exceptions=False) as client:
        providers_file = root / "providers.json"

        # C1: a stored model without "id"
        providers_file.write_text(
            json.dumps({"p1": {"id": "p1", "name": "X", "base_url": "http://x",
                               "api_key": "k", "models": [{"name": "no-id"}]}}),
            encoding="utf-8",
        )
        r_catalog = client.get("/catalog")
        r_providers = client.get("/providers")
        results.append(f"C1 GET /catalog with a model missing 'id': {r_catalog.status_code} {r_catalog.text[:110]}")
        results.append(f"C1b GET /providers in the same state:      {r_providers.status_code}")

        # C3: can an invalid model be created through the API?
        providers_file.unlink()
        r_post = client.post("/providers", json={"name": "New", "baseUrl": "http://y",
                                                 "apiKey": "k", "models": [{"name": "still-no-id"}]})
        results.append(f"C3 POST /providers with a model missing 'id': {r_post.status_code}")
        r_catalog_after = client.get("/catalog")
        results.append(f"C3b GET /catalog after that POST:              {r_catalog_after.status_code}")

        # C4: can the API clear a key? (the UI sends undefined instead)
        # BE-14's fix turns the POST above into a 400, so C4 uses a provider the API accepts.
        if r_post.status_code < 400:
            pid = r_post.json()["id"]
        else:
            r_valid = client.post("/providers", json={"name": "Valid", "baseUrl": "http://y",
                                                      "apiKey": "k", "models": [{"id": "m1", "name": "m1"}]})
            results.append(f"C3c POST /providers with a valid model:        {r_valid.status_code}")
            pid = r_valid.json()["id"]
        r_clear = client.patch(f"/providers/{pid}", json={"apiKey": ""})
        cleared = r_clear.json().get("key_configured") if r_clear.status_code < 400 else None
        results.append(f"C4 PATCH {{'apiKey': ''}} -> {r_clear.status_code}, key_configured={cleared}")

        # C2: a corrupt providers.json
        providers_file.write_text("{not json", encoding="utf-8")
        r_bad = client.get("/providers")
        r_bad_catalog = client.get("/catalog")
        results.append(f"C2 GET /providers with corrupt JSON: {r_bad.status_code} {r_bad.text[:110]}")
        results.append(f"C2b GET /catalog  with corrupt JSON: {r_bad_catalog.status_code}")

    print("\n".join(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
