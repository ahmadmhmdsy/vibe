// apps/vibe/src/lib/__tests__/sse.test.ts
import { describe, it, expect, vi } from "vitest";
import { SSEClient } from "../sse";

describe("SSEClient", () => {
  it("parses SSE data into events", () => {
    const client = new SSEClient("http://localhost:8000");
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

  it("parses onmessage data (EventSource strips the data: prefix)", () => {
    // EventSource's onmessage delivers the data field with the `data: `
    // prefix and the trailing blank line already removed — parse must
    // accept that shape, not only raw SSE frames.
    const client = new SSEClient("http://localhost:8000");
    const event = client.parse('{"seq":2,"type":"turn_complete","payload":{}}');
    expect(event).toEqual({ seq: 2, type: "turn_complete", payload: {} });
    expect(client.lastSeq).toBe(2);
  });

  it("never moves the resume cursor backwards", () => {
    // A replayed frame (or a duplicate from the bus) used to set lastSeq to its
    // own value, so the reconnect asked for events after a seq the client had
    // already passed and re-delivered everything in between.
    const client = new SSEClient("http://localhost:8000");
    client.parse('{"seq":5,"type":"text_chunk","payload":{}}');
    client.parse('{"seq":2,"type":"user/message","payload":{}}');
    expect(client.lastSeq).toBe(5);
    client.parse('{"seq":6,"type":"text_chunk","payload":{}}');
    expect(client.lastSeq).toBe(6);
  });

  it("ignores a frame without a numeric seq", () => {
    const client = new SSEClient("http://localhost:8000");
    client.parse('{"seq":4,"type":"text_chunk","payload":{}}');
    client.parse('{"type":"text_chunk","payload":{}}');
    expect(client.lastSeq).toBe(4);
  });

  it("delivers onmessage events to the connect handler", () => {
    // Integration: connect() wires onmessage through parse, so plain-JSON
    // message data must reach onEvent.
    class MockEventSource {
      onmessage: ((msg: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(public url: string) {
        instances.push(this);
      }
      close() {}
    }
    const instances: MockEventSource[] = [];
    vi.stubGlobal("EventSource", MockEventSource);
    try {
      const client = new SSEClient("http://localhost:8000");
      const onEvent = vi.fn();
      client.connect("sess1", onEvent);
      expect(instances).toHaveLength(1);
      expect(instances[0].url).toBe("http://localhost:8000/sessions/sess1/events?after_seq=0");
      instances[0].onmessage!({ data: '{"seq":3,"type":"text_chunk","payload":{"text":"yo"}}' });
      expect(onEvent).toHaveBeenCalledWith({ seq: 3, type: "text_chunk", payload: { text: "yo" } });
      expect(client.lastSeq).toBe(3);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
