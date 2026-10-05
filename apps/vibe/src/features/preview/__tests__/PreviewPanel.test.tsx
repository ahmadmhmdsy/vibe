// apps/vibe/src/features/preview/__tests__/PreviewPanel.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    getPreview: vi.fn(),
    runPreview: vi.fn(),
    stopPreview: vi.fn(),
  },
}));

import { api } from "../../../lib/api";
import { PreviewPanel } from "../PreviewPanel";
import { usePreviewStore } from "../store";

afterEach(() => {
  cleanup();
  usePreviewStore.setState({ url: null, isRunning: false, loading: false, error: null });
  vi.clearAllMocks();
});

describe("PreviewPanel", () => {
  it("shows the empty state when no preview is running", () => {
    render(<PreviewPanel sessionId="s1" />);
    expect(screen.getByText(/no preview yet/i)).toBeInTheDocument();
  });

  it("run starts the dev server and shows the iframe", async () => {
    vi.mocked(api.runPreview).mockResolvedValue({
      url: "http://127.0.0.1:5173/",
      is_running: true,
    });
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByTitle("App preview")).toBeInTheDocument();
  });

  it("shows an error banner when run fails", async () => {
    vi.mocked(api.runPreview).mockRejectedValue(new Error("API error: 500"));
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 500/);
  });

  it("stop clears the preview", async () => {
    usePreviewStore.setState({ url: "http://127.0.0.1:5173/", isRunning: true });
    vi.mocked(api.stopPreview).mockResolvedValue({ url: null, is_running: false });
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^stop$/i }));
    expect(await screen.findByText(/no preview yet/i)).toBeInTheDocument();
  });
});
