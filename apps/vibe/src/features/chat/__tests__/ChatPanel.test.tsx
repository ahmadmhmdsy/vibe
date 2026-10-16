// apps/vibe/src/features/chat/__tests__/ChatPanel.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  // lib/sse reads API_BASE from this module, and MessageList imports SSEClient.
  API_BASE: "http://localhost:7321",
  api: {
    listApprovals: vi.fn().mockResolvedValue([]),
    getCatalog: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue(null),
    getUsage: vi.fn().mockResolvedValue({ steps: 0 }),
    setSessionModel: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

import { ChatPanel } from "../ChatPanel";
import { useChatStore } from "../store";
import { useSessionsStore } from "../../sessions/store";

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
});

beforeEach(() => {
  useChatStore.setState({
    timelineBySession: {},
    isStreamingBySession: {},
    stopRequested: {},
    pendingDraftBySession: {},
  });
});

describe("ChatPanel", () => {
  it("renders the header, the transcript, and the composer", () => {
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "Conversation transcript" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /attach image/i })).toBeInTheDocument();
  });

  it("shows the active session's title in the panel header", () => {
    useSessionsStore.setState({
      sessions: [
        { id: "s1", title: "Todo app", model: { provider_id: "openai", model_id: "gpt-4o" } },
      ],
      activeId: "s1",
    });
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByRole("heading", { name: "Todo app" })).toBeInTheDocument();
  });

  it("falls back to a plain title before the session is named", () => {
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });
});
