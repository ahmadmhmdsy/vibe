// apps/vibe/src/features/chat/__tests__/MessageList.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { MessageList } from "../MessageList";
import { useChatStore } from "../store";

// Stub the SSE client, capturing the handler so a test can drive events.
const sse = vi.hoisted(() => ({ onEvent: null as null | ((e: unknown) => void) }));
vi.mock("../../../lib/sse", () => ({
  SSEClient: class {
    connect(_sessionId: string, onEvent: (e: unknown) => void) {
      sse.onEvent = onEvent;
    }
    disconnect() {}
  },
}));

// Stub the approval API.
vi.mock("../../../lib/api", () => ({
  api: {
    listApprovals: vi.fn().mockResolvedValue([]),
    approve: vi.fn().mockResolvedValue({ ok: true }),
    deny: vi.fn().mockResolvedValue({ ok: true }),
    getMessages: vi.fn().mockResolvedValue({ messages: [], total: 0 }),
  },
}));

import { api } from "../../../lib/api";

afterEach(cleanup);

describe("MessageList", () => {
  beforeEach(() => {
    sse.onEvent = null;
    useChatStore.setState({
      messagesBySession: { s1: [{ id: "u1", role: "user", content: "hi" }] },
      isStreamingBySession: {},
      streamingMessageIdBySession: {},
      historyTotalBySession: {},
      model: { provider_id: "openai", model_id: "gpt-4o" },
    });
  });

  it("renders messages", () => {
    render(<MessageList sessionId="s1" />);
    expect(screen.getByText(/hi/)).toBeInTheDocument();
  });

  it("fetches approvals on mount", () => {
    render(<MessageList sessionId="s1" />);
    expect(api.listApprovals).toHaveBeenCalledWith("s1");
  });

  it("teaches the loop before the first message", () => {
    useChatStore.setState({ messagesBySession: {}, isStreamingBySession: {} });
    render(<MessageList sessionId="s1" />);
    expect(
      screen.getByRole("heading", { name: /describe the app you want to build/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/dependency installs that fall outside the allowlist/i)).toBeInTheDocument();
  });

  it("loads history for the session", async () => {
    const { findByText } = render(<MessageList sessionId="s1" />);
    // history loads without wiping the in-memory message
    expect(await findByText(/hi/)).toBeInTheDocument();
  });

  it("streams chunks into one message and ends the turn on turn_complete", () => {
    useChatStore.setState({
      messagesBySession: { s1: [{ id: "u1", role: "user", content: "hi" }] },
      isStreamingBySession: { s1: true },
    });
    render(<MessageList sessionId="s1" />);
    act(() => {
      sse.onEvent!({ seq: 2, type: "text_chunk", payload: { text: "Hel" } });
      sse.onEvent!({ seq: 3, type: "text_chunk", payload: { text: "lo" } });
      sse.onEvent!({ seq: 4, type: "turn_complete", payload: {} });
    });
    const messages = useChatStore.getState().messagesBySession.s1;
    expect(messages).toHaveLength(2);
    expect(messages[1]).toMatchObject({ role: "assistant", content: "Hello" });
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(false);
  });

  it("does not offer older messages when the whole history is loaded", () => {
    useChatStore.setState({ historyTotalBySession: { s1: 1 } });
    render(<MessageList sessionId="s1" />);
    expect(screen.queryByRole("button", { name: /load older messages/i })).not.toBeInTheDocument();
  });

  it("offers older messages when the server holds more than the page", () => {
    useChatStore.setState({ historyTotalBySession: { s1: 5 } });
    render(<MessageList sessionId="s1" />);
    expect(screen.getByRole("button", { name: /load older messages/i })).toBeInTheDocument();
  });

  it("ignores unrelated event types", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<MessageList sessionId="s1" />);
    act(() => {
      sse.onEvent!({ seq: 2, type: "tool_call", payload: { name: "write_file" } });
    });
    expect(useChatStore.getState().messagesBySession.s1).toHaveLength(1);
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(true);
  });
});
