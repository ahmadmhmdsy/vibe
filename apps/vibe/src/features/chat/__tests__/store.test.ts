// features/chat/__tests__/store.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { EMPTY_TIMELINE, useChatStore } from "../store";

beforeEach(() => {
  useChatStore.setState({
    timelineBySession: {},
    isStreamingBySession: {},
    stopRequested: {},
    model: { provider_id: "openai", model_id: "gpt-4o" },
  });
});

describe("chat store", () => {
  it("folds a user message into the session timeline", () => {
    useChatStore
      .getState()
      .applyStreamEvent("s1", { seq: 1, type: "user/message", payload: { content: "hi" } });
    const items = useChatStore.getState().timelineBySession.s1.items;
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: "user", content: "hi", pending: false });
  });

  it("keeps a timeline per session", () => {
    useChatStore
      .getState()
      .applyStreamEvent("s1", { seq: 1, type: "user/message", payload: { content: "one" } });
    useChatStore
      .getState()
      .applyStreamEvent("s2", { seq: 1, type: "user/message", payload: { content: "two" } });
    expect(useChatStore.getState().timelineBySession.s1.items[0]).toMatchObject({ content: "one" });
    expect(useChatStore.getState().timelineBySession.s2.items[0]).toMatchObject({ content: "two" });
  });

  it("folds tool calls and results into one row", () => {
    const { applyStreamEvent } = useChatStore.getState();
    applyStreamEvent("s1", {
      seq: 1,
      type: "tool_call",
      payload: { tool_call: { id: "c1", name: "write_file", args: { path: "a.ts" } } },
    });
    applyStreamEvent("s1", {
      seq: 2,
      type: "tool_result",
      payload: { tool_call_id: "c1", name: "write_file", content: "ok", is_error: false },
    });
    const items = useChatStore.getState().timelineBySession.s1.items;
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: "tool", status: "ok", result: "ok" });
  });

  it("adds an optimistic user message and returns its id", () => {
    const id = useChatStore.getState().addOptimisticUserMessage("s1", "pending text");
    const items = useChatStore.getState().timelineBySession.s1.items;
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ id, kind: "user", content: "pending text", pending: true });
  });

  it("removes exactly the item that failed to send", () => {
    const { addOptimisticUserMessage, removeTimelineItem } = useChatStore.getState();
    const doomed = addOptimisticUserMessage("s1", "never arrived");
    addOptimisticUserMessage("s1", "kept");
    removeTimelineItem("s1", doomed);
    const items = useChatStore.getState().timelineBySession.s1.items;
    expect(items.filter((item) => item.kind === "user").map((item) => item.content)).toEqual([
      "kept",
    ]);
  });

  it("resets only the named session", () => {
    const { applyStreamEvent, resetTimeline } = useChatStore.getState();
    applyStreamEvent("s1", { seq: 1, type: "user/message", payload: { content: "one" } });
    applyStreamEvent("s2", { seq: 1, type: "user/message", payload: { content: "two" } });
    resetTimeline("s1");
    expect(useChatStore.getState().timelineBySession.s1.items).toEqual([]);
    expect(useChatStore.getState().timelineBySession.s2.items).toHaveLength(1);
  });

  it("does not write when an event is ignored", () => {
    useChatStore.getState().addOptimisticUserMessage("s1", "hi");
    const before = useChatStore.getState().timelineBySession.s1;
    useChatStore
      .getState()
      .applyStreamEvent("s1", { seq: 0, type: "text_chunk", payload: { text: "" } });
    expect(useChatStore.getState().timelineBySession.s1).toBe(before);
  });

  it("clears the stop latch when the next turn begins", () => {
    const { beginStream, requestStop } = useChatStore.getState();
    beginStream("s1");
    requestStop("s1");
    expect(useChatStore.getState().stopRequested.s1).toBe(true);
    beginStream("s1");
    expect(useChatStore.getState().stopRequested.s1).toBe(false);
  });

  it("keeps streaming state per session", () => {
    const { beginStream, endStream } = useChatStore.getState();
    beginStream("s1");
    endStream("s2");
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(true);
    expect(useChatStore.getState().isStreamingBySession.s2).toBe(false);
  });

  it("exports one shared empty timeline", () => {
    expect(EMPTY_TIMELINE.items).toEqual([]);
    expect(useChatStore.getState().timelineBySession.s9).toBeUndefined();
  });
});
