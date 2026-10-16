# tests/test_custom_providers.py
"""R2-T3/T4: validate provider models, and make the store survive damage.

Ports custom-probe 1-3 from the 2026-10-11 review. The catalog indexed m["id"]
while POST /providers accepted any models list, so a single model without an id
made GET /catalog answer 500 for every client; a truncated providers.json did the
same; and the store's read-modify-write was unlocked, so two concurrent creates
could lose one provider.
"""

import asyncio
import json

from vibe.providers.custom import CustomProvider


def _provider(pid: str) -> CustomProvider:
    return CustomProvider(id=pid, name=pid, base_url="http://x", api_key="k")


# --- R2-T3: model validation and a defensive catalog ----------------------


def test_create_provider_rejects_a_model_without_an_id(client):
    r = client.post("/providers", json={"name": "X", "baseUrl": "http://x", "models": [{"name": "n"}]})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_create_provider_rejects_a_blank_model_id(client):
    r = client.post("/providers", json={"name": "X", "baseUrl": "http://x", "models": [{"id": "  "}]})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_create_provider_rejects_a_duplicate_model_id(client):
    r = client.post(
        "/providers",
        json={
            "name": "X",
            "baseUrl": "http://x",
            "models": [{"id": "m", "name": "a"}, {"id": "m", "name": "b"}],
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_create_provider_defaults_a_missing_model_name(client):
    r = client.post("/providers", json={"name": "X", "baseUrl": "http://x", "models": [{"id": "m"}]})
    assert r.status_code == 201, r.text
    assert r.json()["models"] == [{"id": "m", "name": "m"}]


def test_patch_provider_validates_new_models(client):
    created = client.post("/providers", json={"name": "X", "baseUrl": "http://x", "models": []}).json()
    r = client.patch(f"/providers/{created['id']}", json={"models": [{"name": "no-id"}]})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"


def test_catalog_survives_a_hand_edited_store(client, store_path):
    # A store written by an older version, or edited by hand.
    store_path.write_text(
        json.dumps(
            {
                "p1": {
                    "id": "p1",
                    "name": "X",
                    "base_url": "http://x",
                    "api_key": "k",
                    "models": [{"name": "no-id"}, {"id": "ok", "name": "Fine"}],
                }
            }
        ),
        encoding="utf-8",
    )
    r = client.get("/catalog")
    assert r.status_code == 200, r.text
    # /catalog merges the builtins with the custom store, so look only at p1.
    customs = [p for p in r.json() if p["id"] == "p1"]
    assert len(customs) == 1
    assert [m["id"] for m in customs[0]["models"]] == ["ok"], "the malformed model must be skipped"


# --- R2-T4: a durable, locked store ---------------------------------------


def test_corrupt_store_degrades_to_empty(client, store_path):
    store_path.write_text("{not json", encoding="utf-8")
    assert client.get("/providers").status_code == 200
    assert client.get("/catalog").status_code == 200


def test_unreadable_store_is_quarantined(client, store_path):
    store_path.write_text("{not json", encoding="utf-8")
    client.get("/providers")
    assert list(store_path.parent.glob("providers.json.corrupt-*")), "keep the bad file for inspection"


def test_malformed_entry_does_not_brick_the_store(client, store_path):
    # Valid JSON, wrong shape: one entry is not even a provider.
    store_path.write_text(json.dumps({"p1": {"nonsense": True}}), encoding="utf-8")
    assert client.get("/providers").status_code == 200


def test_concurrent_creates_do_not_lose_a_provider(store):
    async def race():
        await asyncio.gather(*[asyncio.to_thread(store.create, _provider(f"p{i}")) for i in range(5)])

    asyncio.run(race())
    assert len(store.list()) == 5


def test_save_is_atomic_and_leaves_no_tmp_file(store, store_path):
    store.create(_provider("p1"))
    assert store_path.exists()
    assert not list(store_path.parent.glob("*.tmp")), "a temp file must not outlive the save"


def test_store_round_trips_an_extra_model_key(store, store_path):
    # The catalog and the UI pass through keys they do not own (e.g. protocol).
    store.create(
        CustomProvider(
            id="p1",
            name="P",
            base_url="http://x",
            api_key="",
            models=[{"id": "m", "name": "M", "protocol": "openai-chat"}],
        )
    )
    assert store.get("p1").models == [{"id": "m", "name": "M", "protocol": "openai-chat"}]
