// apps/vibe/src/__tests__/App.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("../lib/api", () => ({
  api: {
    listSessions: vi.fn().mockResolvedValue([]),
    getCatalog: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue({
      id: "s1",
      title: "Test session",
      model: { provider_id: "openai", model_id: "gpt-4o" },
    }),
    createSession: vi.fn().mockResolvedValue({ id: "s1" }),
    listProviders: vi.fn().mockResolvedValue([]),
    listApprovals: vi.fn().mockResolvedValue([]),
    getUsage: vi.fn().mockResolvedValue({ steps: 0 }),
    listFiles: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("../lib/sse", () => ({
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

import App from "../App";
import { useSessionsStore } from "../features/sessions/store";

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
});

describe("App shell", () => {
  it("renders the header with the product name", () => {
    render(<App />);
    expect(screen.getByText("vibe")).toBeInTheDocument();
  });

  it("opens settings from the header button and closes via Esc", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("toggles settings with Cmd+,", () => {
    render(<App />);
    fireEvent.keyDown(document, { key: ",", metaKey: true });
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: ",", metaKey: true });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an empty state with a New session CTA instead of a dead end", () => {
    render(<App />);
    expect(screen.getByText(/no session selected/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new session/i })).toBeInTheDocument();
  });
});
