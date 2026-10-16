"""Live bridge check client — see tests/live/server.py for how to run it."""

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:7399"
ok = True


def check(label, cond, detail=""):
    global ok
    ok = ok and bool(cond)
    print(("PASS " if cond else "FAIL ") + label + ((" :: " + str(detail)) if detail else ""))


async def collect(resp, frames, stop_types, done):
    async for line in resp.aiter_lines():
        if line.startswith("data: "):
            frames.append(json.loads(line[6:]))
            if frames[-1]["type"] in stop_types:
                done.set()
                return


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as c:
        check("unknown session id -> 404", (await c.get("/sessions/does-not-exist/messages")).status_code == 404)
        sid = (await c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})).json()["id"]
        check(
            "non-integer after_seq -> 400",
            (await c.get(f"/sessions/{sid}/events", params={"after_seq": "abc"})).status_code == 400,
        )
        check("unknown session preview -> 404", (await c.get("/sessions/does-not-exist/preview")).status_code == 404)
        check(
            "preview state for a real session",
            (await c.get(f"/sessions/{sid}/preview")).json() == {"url": None, "is_running": False},
        )

        pid = (
            await c.post(
                "/providers",
                json={"name": "Live", "baseUrl": "http://old.example/v1", "apiKey": "sk-live", "models": []},
            )
        ).json()["id"]
        r = await c.patch(f"/providers/{pid}", json={"baseUrl": "http://new.example/v1", "name": "Live 2"})
        check(
            "PATCH accepts camelCase",
            r.status_code == 200 and r.json()["baseUrl"] == "http://new.example/v1",
            r.json().get("baseUrl"),
        )
        reread = {p["id"]: p for p in (await c.get("/providers")).json()}[pid]
        check("camelCase persisted on re-read", reread["baseUrl"] == "http://new.example/v1", reread["baseUrl"])
        await c.delete(f"/providers/{pid}")

        # Two subscribers on the same session: every frame must reach both.
        tab1, tab2, done1, done2 = [], [], asyncio.Event(), asyncio.Event()

        async def stream(frames, done):
            async with c.stream("GET", f"/sessions/{sid}/events", params={"after_seq": 0}) as resp:
                check(
                    "SSE content-type",
                    resp.headers.get("content-type", "").startswith("text/event-stream"),
                    resp.headers.get("content-type"),
                )
                await collect(resp, frames, {"turn_complete", "error"}, done)

        t1 = asyncio.create_task(stream(tab1, done1))
        t2 = asyncio.create_task(stream(tab2, done2))
        await asyncio.sleep(0.4)
        r = await c.post(f"/sessions/{sid}/messages", json={"content": "hello"})
        check("send -> 200", r.status_code == 200, r.text[:120])
        for name, done in (("tab1", done1), ("tab2", done2)):
            try:
                await asyncio.wait_for(done.wait(), timeout=20)
            except TimeoutError:
                check(name + " turn_complete arrived", False, "timeout")
        t1.cancel()
        t2.cancel()

        types1 = [f["type"] for f in tab1]
        seqs1 = [f["seq"] for f in tab1]
        check(
            "live stream starts with the user message",
            types1[0] == "user/message" and seqs1[0] == 1,
            list(zip(seqs1, types1, strict=True)),
        )
        check("5 chunks streamed live", types1.count("text_chunk") == 5, types1.count("text_chunk"))
        check("every frame carries seq > 0", all(s > 0 for s in seqs1), seqs1)
        check("seqs strictly increase (no dupes, no gaps back)", seqs1 == sorted(set(seqs1)), seqs1)
        check("turn_complete last", types1[-1] == "turn_complete", types1[-1])
        text = "".join(f["payload"]["text"] for f in tab1 if f["type"] == "text_chunk").strip()
        check("streamed text matches response", text == r.json()["content"].strip(), (text, r.json()["content"]))
        check(
            "both subscribers saw the identical stream",
            [f["seq"] for f in tab2] == seqs1 and [f["type"] for f in tab2] == types1,
            [f["seq"] for f in tab2],
        )

        sid2 = (await c.post("/sessions", json={"model": {"provider_id": "openai", "model_id": "gpt-4o"}})).json()["id"]
        frames2, done2 = [], asyncio.Event()

        async def stream2():
            async with c.stream("GET", f"/sessions/{sid2}/events", params={"after_seq": 0}) as resp:
                await collect(resp, frames2, {"turn_complete", "error"}, done2)

        t3 = asyncio.create_task(stream2())
        await asyncio.sleep(0.4)
        send = asyncio.create_task(c.post(f"/sessions/{sid2}/messages", json={"content": "abort-me"}))
        await asyncio.sleep(1.0)
        r = await c.post(f"/sessions/{sid2}/abort")
        check("abort -> {aborted: true}", r.status_code == 200 and r.json() == {"aborted": True}, r.text[:120])
        resp = await asyncio.wait_for(send, timeout=20)
        check(
            "aborted send returns aborted:true",
            resp.status_code == 200 and resp.json().get("aborted") is True,
            resp.text[:160],
        )
        try:
            await asyncio.wait_for(done2.wait(), timeout=10)
        except TimeoutError:
            check("turn_complete after abort", False, "timeout")
        t3.cancel()
        check("partial text kept", "partial work" in resp.json().get("content", ""), resp.json().get("content"))
        check(
            "turn_complete carries aborted flag", frames2[-1]["payload"].get("aborted") is True, frames2[-1]["payload"]
        )
        check("second abort is a no-op", (await c.post(f"/sessions/{sid2}/abort")).json() == {"aborted": False})
        r = await c.get(f"/sessions/{sid2}/messages")
        check("history has no dangling user message", [m["role"] for m in r.json()] == ["user", "assistant"], r.json())

    print("RESULT " + ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


asyncio.run(main())
