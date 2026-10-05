// apps/vibe/src/features/chat/__tests__/store.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../lib/api", () => ({
  api: {
    getMessages: vi.fn().mockResolvedValue({
      messages: [
        { role: "user", content: "old question" },
        { role: "assistant", content: "old answer" },
      ],
      total: 2,
    }),
  },
}));

import { api } from "../../../lib/api";
import { useChatStore } from "../store";

beforeEach(() => {
  useChatStore.setState({
    messagesBySession: {},
    isStreamingBySession: {},
    streamingMessageIdBySession: {},
    stopRequested: {},
    historyTotalBySession: {},
  });
});

describe("chat store", () => {
  it("gives every message a distinct id", () => {
    const { addMessage } = useChatStore.getState();
    addMessage("s1", { role: "user", content: "one" });
    addMessage("s1", { role: "user", content: "two" });
    const ids = useChatStore.getState().messagesBySession.s1.map((m) => m.id);
    expect(new Set(ids).size).toBe(2);
    expect(ids.every(Boolean)).toBe(true);
  });

  it("appends chunks to a single assistant message", () => {
    const { addMessage, beginStream, appendChunk } = useChatStore.getState();
    addMessage("s1", { role: "user", content: "hi" });
    beginStream("s1");
    appendChunk("s1", "Hel");
    appendChunk("s1", "lo");
    const messages = useChatStore.getState().messagesBySession.s1;
    expect(messages).toHaveLength(2);
    expect(messages[1]).toMatchObject({ role: "assistant", content: "Hello" });
  });

  it("never writes a new turn's text into a finished message", () => {
    const { addMessage, beginStream, appendChunk, endStream } = useChatStore.getState();
    addMessage("s1", { role: "user", content: "one" });
    beginStream("s1");
    appendChunk("s1", "first answer");
    endStream("s1");

    addMessage("s1", { role: "user", content: "two" });
    beginStream("s1");
    appendChunk("s1", "second answer");

    const messages = useChatStore.getState().messagesBySession.s1;
    expect(messages.map((m) => m.content)).toEqual(["one", "first answer", "two", "second answer"]);
  });

  it("starts a fresh message after a stream ends instead of extending the old one", () => {
    const { addMessage, beginStream, appendChunk, endStream } = useChatStore.getState();
    addMessage("s1", { role: "user", content: "hi" });
    beginStream("s1");
    appendChunk("s1", "done");
    endStream("s1");
    expect(useChatStore.getState().streamingMessageIdBySession.s1).toBe(null);

    // A stray late chunk must not mutate the finished message.
    appendChunk("s1", "late");
    const messages = useChatStore.getState().messagesBySession.s1;
    expect(messages[1].content).toBe("done");
    expect(messages[2].content).toBe("late");
  });

  it("clears the stop latch when the next turn begins", () => {
    const { beginStream, requestStop } = useChatStore.getState();
    beginStream("s1");
    requestStop("s1");
    expect(useChatStore.getState().stopRequested.s1).toBe(true);
    beginStream("s1");
    expect(useChatStore.getState().stopRequested.s1).toBe(false);
  });

  it("assigns ids when history loads", async () => {
    await useChatStore.getState().loadHistory("s2");
    const messages = useChatStore.getState().messagesBySession.s2;
    expect(messages).toHaveLength(2);
    expect(messages.every((m) => typeof m.id === "string" && m.id.length > 0)).toBe(true);
  });

  it("records the total so the UI knows whether older messages exist", async () => {
    await useChatStore.getState().loadHistory("s2");
    expect(useChatStore.getState().historyTotalBySession.s2).toBe(2);
  });

  it("prepends the older page without disturbing the current one", async () => {
    vi.mocked(api.getMessages).mockResolvedValueOnce({
      messages: [{ role: "user", content: "older question" }],
      total: 3,
    });
    useChatStore.setState({
      messagesBySession: { s3: [{ id: "a", role: "user", content: "newest" }] },
      historyTotalBySession: { s3: 3 },
    });

    await useChatStore.getState().loadMoreHistory("s3");

    const messages = useChatStore.getState().messagesBySession.s3;
    expect(messages.map((m) => m.content)).toEqual(["older question", "newest"]);
    // The offset is however many the client already held.
    expect(vi.mocked(api.getMessages)).toHaveBeenCalledWith("s3", { limit: 200, offset: 1 });
  });

  it("keeps streaming state per session", () => {
    const { beginStream, endStream } = useChatStore.getState();
    beginStream("s1");
    endStream("s2");
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(true);
    expect(useChatStore.getState().isStreamingBySession.s2).toBe(false);
  });
});
