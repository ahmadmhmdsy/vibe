// apps/vibe/src/features/sessions/__tests__/SessionsPanel.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    listSessions: vi.fn().mockResolvedValue([]),
    getCatalog: vi.fn().mockResolvedValue([]),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    renameSession: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

import { api } from "../../../lib/api";
import { SessionsPanel } from "../SessionsPanel";
import { useSessionsStore } from "../store";

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
  vi.mocked(api.listSessions).mockResolvedValue([]);
  vi.mocked(api.deleteSession).mockResolvedValue(undefined);
});

describe("SessionsPanel", () => {
  it("renders a new session button", () => {
    render(<SessionsPanel />);
    expect(screen.getByRole("button", { name: /new/i })).toBeInTheDocument();
  });

  it("shows an empty state with a CTA when there are no sessions", async () => {
    render(<SessionsPanel />);
    expect(await screen.findByText(/no sessions yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new session/i })).toBeInTheDocument();
  });

  it("asks for confirmation before deleting a session", async () => {
    const session = {
      id: "s1",
      title: "My app",
      model: { provider_id: "openai", model_id: "gpt-4o" },
      created_at: "2026-09-29",
      updated_at: "2026-09-29",
    };
    vi.mocked(api.listSessions).mockResolvedValue([session]);
    useSessionsStore.setState({ sessions: [session], activeId: "s1" });
    render(<SessionsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete My app" }));
    expect(screen.getByRole("alertdialog", { name: "Delete session?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(vi.mocked(api.deleteSession)).toHaveBeenCalledWith("s1");
  });

  it("shows an error banner when loading sessions fails", async () => {
    vi.mocked(api.listSessions).mockRejectedValueOnce(new Error("API error: 400"));
    render(<SessionsPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 400/);
  });
});
