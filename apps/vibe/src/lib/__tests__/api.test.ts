// apps/vibe/src/lib/__tests__/api.test.ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { api, ApiError } from "../api";

/** Stub fetch with a hand-built response. Only the fields the code reads are
 * needed, so the whole Response interface would be noise. */
function stubFetch(partial: Record<string, unknown>) {
  const fn = vi.fn().mockResolvedValue(partial as unknown as Response);
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api error handling", () => {
  it("carries the backend error code so a caller can branch on it", async () => {
    stubFetch({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "session_not_found", message: "session not found" } }),
    });
    const err = (await api.getSession("nope").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.code).toBe("session_not_found");
    expect(err.message).toBe("session not found");
  });

  it("falls back to a generic message when the body is not the shared shape", async () => {
    stubFetch({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError("not json");
      },
    });
    const err = (await api.listSessions().catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(err.code).toBeUndefined();
    expect(err.message).toBe("API error: 502");
  });
});

describe("api body parsing", () => {
  it("resolves a delete that answers 204 with no body", async () => {
    // resp.json() rejects on an empty stream, so this used to throw for a
    // request the server had already carried out.
    stubFetch({ ok: true, status: 204, text: async () => "" });
    await expect(api.deleteSession("s1")).resolves.toBeUndefined();
  });

  it("reads the pagination total from the header", async () => {
    stubFetch({
      ok: true,
      status: 200,
      text: async () => JSON.stringify([{ role: "user", content: "hi" }]),
      headers: new Headers({ "X-Total-Count": "9" }),
    });
    const page = await api.getMessages("s1", { limit: 1 });
    expect(page.messages).toEqual([{ role: "user", content: "hi" }]);
    expect(page.total).toBe(9);
  });

  it("defaults the total to the page length when the header is absent", async () => {
    stubFetch({
      ok: true,
      status: 200,
      text: async () => JSON.stringify([{ role: "user", content: "hi" }]),
      headers: new Headers(),
    });
    expect((await api.getMessages("s1")).total).toBe(1);
  });

  it("sends the page window as query parameters", async () => {
    const fetchMock = stubFetch({
      ok: true,
      status: 200,
      text: async () => "[]",
      headers: new Headers(),
    });
    await api.getMessages("s1", { limit: 1, offset: 2 });
    expect(String(fetchMock.mock.calls[0][0])).toContain("/sessions/s1/messages?limit=1&offset=2");
  });
});
