// apps/vibe/src/features/chat/__tests__/Composer.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    sendMessage: vi.fn().mockResolvedValue({ content: "ok" }),
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
  useChatStore.setState({ messagesBySession: {}, isStreamingBySession: {}, model: { provider_id: "openai", model_id: "gpt-4o" } });
  vi.mocked(api.sendMessage).mockResolvedValue({ content: "ok" });
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

  it("shows an error and keeps the text when sending fails", async () => {
    vi.mocked(api.sendMessage).mockRejectedValueOnce(new ApiError("API error: 400", 400));
    render(<Composer sessionId="s1" />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 400/);
    expect(screen.getByRole("textbox")).toHaveValue("hello");
  });

  it("shows a stop button while streaming", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
  });

  it("stop button requests a stop and clears the indicator", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<Composer sessionId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(useChatStore.getState().stopRequested.s1).toBe(true);
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(false);
  });
});
