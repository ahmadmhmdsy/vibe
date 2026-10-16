// apps/vibe/src/features/preview/__tests__/PreviewPanel.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";

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
  usePreviewStore.setState({ bySession: {} });
  vi.clearAllMocks();
});

describe("PreviewPanel", () => {
  it("shows the not-running state with a run action", () => {
    render(<PreviewPanel sessionId="s1" />);
    expect(screen.getByText(/preview is not running/i)).toBeInTheDocument();
    // The chip carries the word twice on purpose: once visibly, once as the
    // dot's accessible label. Assert on the badge to stay unambiguous.
    const chip = document.querySelector(".badge");
    expect(chip).not.toBeNull();
    expect(within(chip as HTMLElement).getAllByText("Stopped").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /run preview/i })).toBeInTheDocument();
    // One Run control, not a Run plus a permanently-visible Stop.
    expect(screen.queryByRole("button", { name: /^stop$/i })).not.toBeInTheDocument();
  });

  it("uses the layout contract and leaves the header title to the shell tabs", () => {
    render(<PreviewPanel sessionId="s1" />);
    const body = screen.getByTestId("preview-layout");
    expect(body).toHaveClass("panel-body");
    expect(body).toHaveAttribute("data-direction", "column");
    expect(document.querySelector(".panel-title")).toBeNull();
  });

  it("run starts the dev server and shows the iframe", async () => {
    vi.mocked(api.runPreview).mockResolvedValue({
      url: "http://127.0.0.1:5173/",
      is_running: true,
    });
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByTitle("App preview")).toBeInTheDocument();
    // Running exposes Stop in place of Run.
    expect(screen.getByRole("button", { name: /^stop$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^run$/i })).not.toBeInTheDocument();
  });

  it("shows the running state and the URL in the header", async () => {
    vi.mocked(api.runPreview).mockResolvedValue({
      url: "http://127.0.0.1:5173/",
      is_running: true,
    });
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    await screen.findByTitle("App preview");

    expect(
      within(document.querySelector(".badge") as HTMLElement).getAllByText("Running").length
    ).toBeGreaterThan(0);
    // The scheme is dropped for display; the full URL stays available as a title.
    expect(screen.getByTitle("http://127.0.0.1:5173/")).toHaveTextContent("127.0.0.1:5173/");
    expect(screen.getByRole("button", { name: "Copy preview URL" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open preview in a new tab" })).toBeInTheDocument();
  });

  it("shows an error banner when run fails", async () => {
    vi.mocked(api.runPreview).mockRejectedValue(new Error("API error: 500"));
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 500/);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("stop clears the preview", async () => {
    usePreviewStore.setState({
      bySession: {
        s1: { url: "http://127.0.0.1:5173/", isRunning: true, loading: false, error: null },
      },
    });
    vi.mocked(api.stopPreview).mockResolvedValue({ url: null, is_running: false });
    render(<PreviewPanel sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /^stop$/i }));
    expect(await screen.findByText(/preview is not running/i)).toBeInTheDocument();
  });

  it("does not show another session's preview", () => {
    // One global url/status leaked a running dev server into every session.
    usePreviewStore.setState({
      bySession: {
        s2: { url: "http://127.0.0.1:9999/", isRunning: true, loading: false, error: null },
      },
    });
    render(<PreviewPanel sessionId="s1" />);
    expect(screen.getByText(/preview is not running/i)).toBeInTheDocument();
    expect(screen.queryByTitle("App preview")).not.toBeInTheDocument();
  });

  it("pauses the status poll while it is not the active panel", async () => {
    vi.useFakeTimers();
    try {
      render(<PreviewPanel sessionId="s1" active={false} />);
      await vi.advanceTimersByTimeAsync(5000);
      expect(vi.mocked(api.getPreview)).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("polls the status while it is the active panel", async () => {
    vi.mocked(api.getPreview).mockResolvedValue({ url: null, is_running: false });
    vi.useFakeTimers();
    try {
      render(<PreviewPanel sessionId="s1" active />);
      await vi.advanceTimersByTimeAsync(5000);
      expect(vi.mocked(api.getPreview).mock.calls.length).toBeGreaterThan(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
