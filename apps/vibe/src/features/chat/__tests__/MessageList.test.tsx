// apps/vibe/src/features/chat/__tests__/MessageList.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  },
}));

import { api } from "../../../lib/api";

describe("MessageList", () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [{ role: "user", content: "hi" }], isStreaming: false, model: { provider_id: "openai", model_id: "gpt-4o" } });
  });

  it("renders messages", () => {
    render(<MessageList sessionId="s1" />);
    expect(screen.getByText(/hi/)).toBeInTheDocument();
  });

  it("fetches approvals on mount", () => {
    render(<MessageList sessionId="s1" />);
    expect(api.listApprovals).toHaveBeenCalledWith("s1");
  });
});
