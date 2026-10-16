// features/chat/__tests__/timeline.test.ts
//
// The ordering rules in the timeline reducer are the part most likely to break
// silently, so they are pinned here rather than exercised through the DOM.

import { beforeEach, describe, expect, it } from "vitest";
import {
  addOptimisticUser,
  applyEvent,
  applyEvents,
  emptyTimeline,
  removeItem,
  resetItemIds,
  type TimelineState,
} from "../timeline";
import type { StreamEvent } from "../../../lib/sse";

const event = (seq: number, type: string, payload: Record<string, unknown> = {}): StreamEvent => ({
  seq,
  type,
  payload,
});

const fold = (events: StreamEvent[], start: TimelineState = emptyTimeline()) =>
  applyEvents(start, events);

const kinds = (state: TimelineState) => state.items.map((item) => item.kind);

beforeEach(() => {
  resetItemIds();
});

describe("timeline reducer", () => {
  it("replays a stored log in order", () => {
    const state = fold([
      event(1, "user/message", { content: "build a todo app" }),
      event(2, "assistant/message", { content: "Done." }),
    ]);

    expect(kinds(state)).toEqual(["user", "assistant"]);
    expect(state.lastSeq).toBe(2);
    expect(state.items[0]).toMatchObject({
      kind: "user",
      content: "build a todo app",
      pending: false,
    });
  });

  it("ignores a stored event it has already folded", () => {
    const once = fold([
      event(1, "user/message", { content: "hi" }),
      event(2, "assistant/message", { content: "ok" }),
    ]);
    const twice = applyEvent(once, event(2, "assistant/message", { content: "ok" }));

    expect(twice.items).toHaveLength(2);
  });

  it("does not let an ephemeral text_chunk hide the stored event sharing its seq", () => {
    // The backend hands text_chunk event_log.next_seq(sid), so a chunk and the
    // assistant/message that finalizes it can carry the same seq. If the chunk
    // moved the cursor, the stored message would be dropped.
    const state = fold([
      event(1, "user/message", { content: "hi" }),
      event(2, "text_chunk", { text: "Hel" }),
      event(2, "text_chunk", { text: "lo" }),
      event(2, "assistant/message", { content: "Hello" }),
    ]);

    expect(kinds(state)).toEqual(["user", "assistant"]);
    expect(state.items[1]).toMatchObject({ content: "Hello", streaming: false });
    expect(state.lastSeq).toBe(2);
  });

  it("finalizes the streamed bubble instead of appending a second one", () => {
    const state = fold([
      event(1, "text_chunk", { text: "Wor" }),
      event(2, "text_chunk", { text: "king" }),
      event(3, "assistant/message", { content: "Working" }),
    ]);

    expect(state.items).toHaveLength(1);
    expect(state.items[0]).toMatchObject({
      kind: "assistant",
      content: "Working",
      streaming: false,
    });
    expect(state.streamingId).toBeNull();
  });

  it("opens a bubble on the first chunk and appends to it afterwards", () => {
    const first = applyEvent(emptyTimeline(), event(0, "text_chunk", { text: "a" }));
    const second = applyEvent(first, event(0, "text_chunk", { text: "b" }));

    expect(second.items).toHaveLength(1);
    expect(second.items[0]).toMatchObject({ content: "ab", streaming: true });
  });

  it("pairs a tool result with its call rather than adding a row", () => {
    const state = fold([
      event(1, "tool_call", {
        tool_call: { id: "c1", name: "write_file", args: { path: "a.ts" } },
      }),
      event(2, "tool_result", {
        tool_call_id: "c1",
        name: "write_file",
        content: "wrote a.ts",
        is_error: false,
      }),
    ]);

    expect(state.items).toHaveLength(1);
    expect(state.items[0]).toMatchObject({
      kind: "tool",
      name: "write_file",
      status: "ok",
      result: "wrote a.ts",
    });
  });

  it("keeps a tool result whose call was never seen", () => {
    const state = applyEvent(
      emptyTimeline(),
      event(9, "tool_result", {
        tool_call_id: "ghost",
        name: "run_command",
        content: "boom",
        is_error: true,
      })
    );

    expect(state.items).toHaveLength(1);
    expect(state.items[0]).toMatchObject({ kind: "tool", callId: "ghost", status: "error" });
  });

  it("closes the open bubble when a tool call starts", () => {
    const state = fold([
      event(1, "text_chunk", { text: "Let me look." }),
      event(2, "tool_call", { tool_call: { id: "c1", name: "read_file", args: {} } }),
      event(3, "text_chunk", { text: "Found it." }),
    ]);

    expect(kinds(state)).toEqual(["assistant", "tool", "assistant"]);
    expect(state.items[0]).toMatchObject({ content: "Let me look.", streaming: false });
    expect(state.items[2]).toMatchObject({ content: "Found it.", streaming: true });
  });

  it("finalizes an open stream on turn_complete", () => {
    const state = fold([
      event(1, "text_chunk", { text: "partial" }),
      event(2, "turn_complete", {}),
    ]);

    expect(state.items[0]).toMatchObject({ streaming: false });
    expect(state.streamingId).toBeNull();
  });

  it("records an aborted turn as a warning notice", () => {
    const state = fold([event(1, "turn_complete", { aborted: true })]);

    expect(state.items[0]).toMatchObject({ kind: "notice", tone: "warning", content: "Stopped." });
  });

  it("turns a stream error into an error item", () => {
    const state = applyEvent(
      emptyTimeline(),
      event(1, "error", { message: "provider unreachable" })
    );

    expect(state.items[0]).toMatchObject({ kind: "error", content: "provider unreachable" });
  });

  it("confirms the optimistic user message instead of duplicating it", () => {
    const optimistic = addOptimisticUser(emptyTimeline(), "hello");
    expect(optimistic.items[0]).toMatchObject({ kind: "user", pending: true, seq: 0 });

    const confirmed = applyEvent(optimistic, event(1, "user/message", { content: "hello" }));

    expect(confirmed.items).toHaveLength(1);
    expect(confirmed.items[0]).toMatchObject({ kind: "user", pending: false, seq: 1 });
  });

  it("appends a user message that was not sent optimistically", () => {
    const state = applyEvent(
      emptyTimeline(),
      event(4, "user/message", { content: "from another tab" })
    );

    expect(state.items).toHaveLength(1);
    expect(state.items[0]).toMatchObject({ pending: false });
  });

  it("removes an optimistic message by id", () => {
    const optimistic = addOptimisticUser(emptyTimeline(), "never sent");
    const id = optimistic.items[0].id;

    expect(removeItem(optimistic, id).items).toHaveLength(0);
  });

  it("advances the cursor past an unknown event so a replay cannot loop", () => {
    const state = applyEvent(emptyTimeline(), event(7, "something/new", {}));

    expect(state.items).toHaveLength(0);
    expect(state.lastSeq).toBe(7);
  });

  it("is stable when a stored event arrives with no seq", () => {
    const state = applyEvent(emptyTimeline(), event(0, "user/message", { content: "x" }));

    expect(state.items).toHaveLength(1);
    expect(state.lastSeq).toBe(0);
  });

  // The two error branches used to spread closeStream(state) and then append to
  // state.items, throwing away the array closeStream had just closed. The open
  // bubble kept streaming: true, so its caret blinked forever.
  it("closes the open assistant bubble when an assistant error arrives mid-stream", () => {
    const streaming = fold([
      event(1, "user/message", { content: "build it" }),
      event(2, "text_chunk", { text: "working" }),
    ]);
    expect(streaming.streamingId).not.toBeNull();

    const failed = applyEvent(streaming, event(3, "assistant/error", { content: "rate limited" }));

    expect(failed.streamingId).toBeNull();
    expect(failed.items.map((item) => item.kind)).toEqual(["user", "assistant", "error"]);
    expect(failed.items.find((item) => item.kind === "assistant")).toMatchObject({
      streaming: false,
      content: "working",
    });
  });

  it("closes the open assistant bubble when a stream error arrives mid-stream", () => {
    const streaming = fold([
      event(1, "user/message", { content: "build it" }),
      event(2, "text_chunk", { text: "working" }),
    ]);

    const failed = applyEvent(streaming, event(3, "error", { message: "socket closed" }));

    expect(failed.streamingId).toBeNull();
    expect(failed.items.find((item) => item.kind === "assistant")).toMatchObject({
      streaming: false,
    });
    expect(failed.items[failed.items.length - 1]).toMatchObject({
      kind: "error",
      content: "socket closed",
    });
  });

  it("leaves only the newest bubble streaming after a mid-stream error", () => {
    // The visible symptom of the discarded array: the closed bubble still
    // claimed to be streaming, so two bubbles animated at once.
    const state = fold([
      event(1, "text_chunk", { text: "one" }),
      event(2, "error", { message: "blip" }),
      event(3, "text_chunk", { text: "two" }),
    ]);

    const live = state.items.filter((item) => item.kind === "assistant" && item.streaming);

    expect(live).toHaveLength(1);
    expect(live[0]).toMatchObject({ content: "two" });
  });
});
