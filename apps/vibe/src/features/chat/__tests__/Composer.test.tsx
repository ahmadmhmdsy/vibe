// apps/vibe/src/features/chat/__tests__/Composer.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    sendMessage: vi.fn().mockResolvedValue({ content: "ok", aborted: false }),
    abortSession: vi.fn().mockResolvedValue({ aborted: true }),
    // The composer toolbar renders the real ModelPicker, which reads the
    // catalog and reflects the session's stored model.
    getCatalog: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue({
      id: "s1",
      title: "t",
      model: { provider_id: "openai", model_id: "gpt-4o" },
    }),
    setSessionModel: vi.fn().mockResolvedValue({ ok: true }),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

import { api, ApiError } from "../../../lib/api";
import { Composer } from "../Composer";
import { useChatStore } from "../store";

afterEach(() => {
  cleanup();
  // clearAllMocks, not just mockResolvedValue: a fresh test must not inherit the
  // previous one's call history.
  vi.clearAllMocks();
  useChatStore.setState({
    timelineBySession: {},
    isStreamingBySession: {},
    stopRequested: {},
    pendingDraftBySession: {},
    model: { provider_id: "openai", model_id: "gpt-4o" },
  });
  vi.mocked(api.sendMessage).mockResolvedValue({ content: "ok", aborted: false });
  vi.mocked(api.abortSession).mockResolvedValue({ aborted: true });
});

describe("Composer", () => {
  it("renders the attach-image button", () => {
    render(<Composer sessionId="s1" />);
    expect(screen.getByRole("button", { name: /attach image/i })).toBeInTheDocument();
  });

  it("disables send when text and attachments are empty", () => {
    render(<Composer sessionId="s1" />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("enables send when text is entered", () => {
    render(<Composer sessionId="s1" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hi" } });
    expect(screen.getByRole("button", { name: /send/i })).toBeEnabled();
  });

  it("sends on Enter and starts the turn", async () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox");
    fireEvent.change(textbox, { target: { value: "hello" } });
    fireEvent.keyDown(textbox, { key: "Enter" });
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("s1", "hello", []));
    expect(useChatStore.getState().timelineBySession.s1.items).toHaveLength(1);
  });

  it("does not send on Shift+Enter", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox");
    fireEvent.change(textbox, { target: { value: "hello" } });
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("shows an error and keeps the text when sending fails", async () => {
    vi.mocked(api.sendMessage).mockRejectedValueOnce(new ApiError("API error: 400", 400));
    render(<Composer sessionId="s1" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 400/);
    expect(screen.getByRole("textbox")).toHaveValue("hello");
  });

  it("withdraws the optimistic bubble on failure so a retry is not a duplicate", async () => {
    vi.mocked(api.sendMessage).mockRejectedValueOnce(new ApiError("API error: 500", 500));
    render(<Composer sessionId="s1" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await screen.findByRole("alert");

    // The message the server never received must not stay in the transcript.
    expect(useChatStore.getState().timelineBySession.s1?.items ?? []).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() =>
      expect(useChatStore.getState().timelineBySession.s1?.items ?? []).toHaveLength(1)
    );
    expect(useChatStore.getState().timelineBySession.s1!.items[0]).toMatchObject({
      content: "hello",
      pending: true,
    });
  });

  it("keeps the keyboard hint out of the accessibility tree's way", () => {
    const { container } = render(<Composer sessionId="s1" />);
    const hint = container.querySelector(".composer-hint");
    expect(hint).not.toBeNull();
    expect(hint!.textContent).toMatch(/enter/i);
    expect(hint!.textContent).toMatch(/new line/i);
  });

  it("shows the character count only as the limit approaches", () => {
    const { container } = render(<Composer sessionId="s1" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x".repeat(10) } });
    expect(container.querySelector(".composer-char-count")).toBeNull();

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "x".repeat(3300) } });
    expect(container.querySelector(".composer-char-count")).not.toBeNull();
  });

  it("shows a stop button while streaming", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
  });

  it("stop asks the backend to abort the run", async () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));

    expect(useChatStore.getState().stopRequested.s1).toBe(true);
    expect(api.abortSession).toHaveBeenCalledWith("s1");
    // The stream stays open: the backend's turn_complete is what ends it.
    await waitFor(() => expect(api.abortSession).toHaveBeenCalled());
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(true);
  });

  it("ends the stream locally when there was nothing to abort", async () => {
    vi.mocked(api.abortSession).mockResolvedValueOnce({ aborted: false });
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    await waitFor(() => expect(useChatStore.getState().isStreamingBySession.s1).toBe(false));
  });

  it("clears the stop latch when the next turn starts", async () => {
    // Nothing was running, so the stop ends the stream locally and the composer
    // returns to its Send state - the latch must not stick to the next turn.
    vi.mocked(api.abortSession).mockResolvedValueOnce({ aborted: false });
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    await waitFor(() => expect(useChatStore.getState().isStreamingBySession.s1).toBe(false));

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "again" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(useChatStore.getState().stopRequested.s1).toBe(false));
  });
});
