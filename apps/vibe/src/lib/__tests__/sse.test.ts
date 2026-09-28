// apps/vibe/src/lib/__tests__/sse.test.ts
import { describe, it, expect, vi } from "vitest";
import { SSEClient } from "../sse";

describe("SSEClient", () => {
  it("parses SSE data into events", () => {
    const client = new SSEClient("http://localhost:8000");
    const onEvent = vi.fn();
    // simulate a parsed event
    const event = client.parse('data: {"seq":1,"type":"text_chunk","payload":{"text":"hi"}}\n\n');
    expect(event).toEqual({ seq: 1, type: "text_chunk", payload: { text: "hi" } });
  });

  it("reconnects with last-seen seq", () => {
    const client = new SSEClient("http://localhost:8000");
    expect(client.lastSeq).toBe(0);
    client.parse('data: {"seq":5,"type":"text_chunk","payload":{}}\n\n');
    expect(client.lastSeq).toBe(5);
  });
});
