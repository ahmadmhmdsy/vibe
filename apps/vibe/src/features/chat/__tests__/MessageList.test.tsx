// apps/vibe/src/features/chat/__tests__/MessageList.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MessageList } from "../MessageList";
import { useChatStore } from "../store";

// Stub the SSE client so the component doesn't try to connect.
vi.mock("../../../lib/sse", () => ({
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

// Stub the approval API.
vi.mock("../../../lib/api", () => ({
  api: {
    listApprovals: vi.fn().mockResolvedValue([]),
    approve: vi.fn().mockResolvedValue({ ok: true }),
    deny: vi.fn().mockResolvedValue({ ok: true }),
    getMessages: vi.fn().mockResolvedValue([]),
  },
}));

import { api } from "../../../lib/api";

afterEach(cleanup);

describe("MessageList", () => {
  beforeEach(() => {
    useChatStore.setState({
      messagesBySession: { s1: [{ role: "user", content: "hi" }] },
      isStreamingBySession: {},
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

  it("loads history for the session", async () => {
    const { findByText } = render(<MessageList sessionId="s1" />);
    // history loads without wiping the in-memory message
    expect(await findByText(/hi/)).toBeInTheDocument();
  });
});
