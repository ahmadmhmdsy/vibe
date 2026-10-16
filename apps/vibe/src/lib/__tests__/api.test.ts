// apps/vibe/src/lib/__tests__/api.test.ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { API_BASE, api, ApiError } from "../api";
import { SSEClient } from "../sse";

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
// R6-T7 (L-7): the frontend has exactly one API origin. The REST client and the
// SSE client used to build their own copies of the default, so a changed port or
// a VITE_API_URL override could leave the chat stream pointing somewhere the API
// client was not. This is the guardrail that keeps it single.

/** Every source file, loaded as text by Vite itself.
 *
 * import.meta.glob reads the real files without node:fs, so this guardrail adds
 * no dependency the app does not already ship and needs no node typings.
 */
const SOURCES = import.meta.glob("/src/**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;
const ORIGIN = /localhost|127\.0\.0\.1/;
/** The one file allowed to name a default origin. */
const API_HOME = "src/lib/api.ts";

const asPosix = (key: string) => key.replace(/^\//, "");

describe("one API origin", () => {
  it("builds every API URL from the single base", () => {
    // Control: the scanner must see the pattern at all, otherwise an empty
    // offender list would only prove the regex is wrong.
    expect(ORIGIN.test('const u = "http://localhost:7321/sessions";')).toBe(true);

    // Control: the glob must actually have read the tree, or an empty offender
    // list would only prove the pattern matched nothing.
    expect(Object.keys(SOURCES).length).toBeGreaterThan(20);

    const offenders = Object.entries(SOURCES)
      .filter(([key]) => !key.includes("__tests__"))
      .filter(([key]) => asPosix(key) !== API_HOME)
      .filter(([, text]) => ORIGIN.test(text))
      .map(([key]) => asPosix(key));
    expect(offenders).toEqual([]);

    // ...and the one allowed home really does hold the default, so the empty
    // result above is not an artefact of the file having moved or gone empty.
    expect(ORIGIN.test(SOURCES["/src/lib/api.ts"])).toBe(true);
  });

  it("defaults the SSE client to the shared base", () => {
    const urls: string[] = [];
    class FakeEventSource {
      onopen: (() => void) | null = null;
      onmessage: ((m: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      url: string;
      constructor(url: string) {
        this.url = url;
        urls.push(url);
      }
      close(): void {}
    }
    vi.stubGlobal("EventSource", FakeEventSource);

    const client = new SSEClient();
    client.connect("sess1", () => {});
    expect(urls[0]).toBe(API_BASE + "/sessions/sess1/events?after_seq=0");
    client.disconnect();
  });
});
