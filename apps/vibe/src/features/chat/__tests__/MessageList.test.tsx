// apps/vibe/src/features/chat/__tests__/MessageList.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import type { StreamEvent } from "../../../lib/sse";
import { MessageList } from "../MessageList";
import { useChatStore } from "../store";

// Stub the SSE client, capturing the handler so a test can drive events.
const sse = vi.hoisted(() => ({ onEvent: null as null | ((e: StreamEvent) => void) }));
vi.mock("../../../lib/sse", () => ({
  // timeline.ts value-imports this set, so the mock has to provide it.
  EPHEMERAL_EVENT_TYPES: new Set(["text_chunk"]),
  SSEClient: class {
    connect(_sessionId: string, onEvent: (e: StreamEvent) => void) {
      sse.onEvent = onEvent;
    }
    disconnect() {}
    retry() {}
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

afterEach(cleanup);

const emptyStore = () =>
  useChatStore.setState({
    timelineBySession: {},
    isStreamingBySession: {},
    stopRequested: {},
    pendingDraftBySession: {},
    model: { provider_id: "openai", model_id: "gpt-4o" },
  });

const emit = (event: StreamEvent) => {
  act(() => {
    sse.onEvent!(event);
  });
};

describe("MessageList", () => {
  beforeEach(() => {
    sse.onEvent = null;
    emptyStore();
  });

  it("rehydrates the transcript from the stream and drops a stale one", () => {
    // Something left over from a previous connect must not survive the reset.
    useChatStore
      .getState()
      .applyStreamEvent("s1", { seq: 1, type: "user/message", payload: { content: "stale" } });
    render(<MessageList sessionId="s1" />);
    expect(screen.queryByText("stale")).not.toBeInTheDocument();

    emit({ seq: 1, type: "user/message", payload: { content: "hi" } });
    expect(screen.getByText("hi")).toBeInTheDocument();
    expect(screen.getByRole("log", { name: "Conversation transcript" })).toBeInTheDocument();
  });

  it("fetches approvals on mount", () => {
    render(<MessageList sessionId="s1" />);
    expect(api.listApprovals).toHaveBeenCalledWith("s1");
  });

  it("teaches the loop before the first message", () => {
    render(<MessageList sessionId="s1" />);
    expect(
      screen.getByRole("heading", { name: /describe the app you want to build/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/installs dependencies/i)).toBeInTheDocument();
  });

  it("renders every event type the server publishes", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    render(<MessageList sessionId="s1" />);

    emit({ seq: 1, type: "assistant/message", payload: { content: "On it." } });
    emit({
      seq: 2,
      type: "tool_call",
      payload: { tool_call: { id: "c1", name: "write_file", args: { path: "src/App.tsx" } } },
    });
    expect(screen.getByText("On it.")).toBeInTheDocument();

    const row = screen.getByRole("button", {
      name: /write_file src\/App\.tsx.*running/i,
    });
    expect(row).toBeInTheDocument();

    emit({
      seq: 3,
      type: "tool_result",
      payload: {
        tool_call_id: "c1",
        name: "write_file",
        content: "wrote 12 lines",
        is_error: false,
      },
    });
    expect(
      screen.getByRole("button", { name: /write_file src\/App\.tsx.*done/i })
    ).toBeInTheDocument();

    // The raw output lives behind the row, not in the main column.
    fireEvent.click(row);
    expect(screen.getByText(/wrote 12 lines/)).toBeInTheDocument();

    // "Done" would be ambiguous: it is also the tool row's status word.
    emit({ seq: 4, type: "text_chunk", payload: { text: "All set" } });
    expect(screen.getByText("All set")).toBeInTheDocument();

    emit({ seq: 5, type: "turn_complete", payload: {} });
    expect(useChatStore.getState().isStreamingBySession.s1).toBe(false);
    expect(useChatStore.getState().timelineBySession.s1.items).toHaveLength(3);
  });

  it("renders a stopped notice when the turn was aborted", () => {
    render(<MessageList sessionId="s1" />);
    emit({ seq: 1, type: "turn_complete", payload: { aborted: true } });
    expect(screen.getByText("Stopped.")).toBeInTheDocument();
  });

  it("surfaces errors from both error events", () => {
    render(<MessageList sessionId="s1" />);
    emit({ seq: 1, type: "error", payload: { message: "provider exploded" } });
    emit({ seq: 2, type: "assistant/error", payload: { content: "the model returned junk" } });
    expect(screen.getByText("provider exploded")).toBeInTheDocument();
    expect(screen.getByText("the model returned junk")).toBeInTheDocument();
  });

  it("ignores an unknown event type but still advances the cursor", () => {
    render(<MessageList sessionId="s1" />);
    emit({ seq: 1, type: "totally/unknown", payload: {} });
    expect(useChatStore.getState().timelineBySession.s1.items).toHaveLength(0);
    expect(useChatStore.getState().timelineBySession.s1.lastSeq).toBe(1);
  });

  it("keeps one live region in the transcript while streaming", () => {
    useChatStore.setState({ isStreamingBySession: { s1: true } });
    const { container } = render(<MessageList sessionId="s1" />);
    const log = container.querySelector(".message-log")!;
    expect(log).toHaveAttribute("role", "log");
    // The spinner and its label sit inside the log; a nested status region
    // would announce the same thing twice.
    expect(log.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0);
    expect(screen.getByText(/agent is working/i)).toBeInTheDocument();
  });

  /** jsdom has no layout: give the list a measurable box and a writable scrollTop. */
  function installScrollMetrics(
    el: HTMLElement,
    { scrollHeight, clientHeight, top }: { scrollHeight: number; clientHeight: number; top: number }
  ) {
    const pos = { top };
    Object.defineProperty(el, "scrollHeight", { value: scrollHeight, configurable: true });
    Object.defineProperty(el, "clientHeight", { value: clientHeight, configurable: true });
    Object.defineProperty(el, "scrollTop", {
      configurable: true,
      get: () => pos.top,
      set: (v: number) => {
        pos.top = v;
      },
    });
    return pos;
  }

  it("follows new content while the user is at the bottom", () => {
    const { container } = render(<MessageList sessionId="s1" />);
    const list = container.querySelector(".message-list") as HTMLElement;
    const pos = installScrollMetrics(list, { scrollHeight: 1000, clientHeight: 300, top: 700 });
    fireEvent.scroll(list);

    emit({ seq: 1, type: "text_chunk", payload: { text: "more" } });
    expect(pos.top).toBe(1000);
  });

  it("stops following once the user scrolls up and offers a way back", () => {
    const { container } = render(<MessageList sessionId="s1" />);
    const list = container.querySelector(".message-list") as HTMLElement;
    const pos = installScrollMetrics(list, { scrollHeight: 1000, clientHeight: 300, top: 120 });
    fireEvent.scroll(list);

    expect(screen.getByRole("button", { name: /jump to latest/i })).toBeInTheDocument();

    emit({ seq: 1, type: "text_chunk", payload: { text: "streamed" } });
    // Reading earlier messages is not undone by the next streamed chunk.
    expect(pos.top).toBe(120);

    fireEvent.click(screen.getByRole("button", { name: /jump to latest/i }));
    expect(pos.top).toBe(1000);
    expect(screen.queryByRole("button", { name: /jump to latest/i })).not.toBeInTheDocument();
  });

  it("shows no jump control when the transcript cannot scroll at all", () => {
    // scrollHeight == clientHeight means the log is already at the bottom, and
    // no scroll event ever fires to say so.
    const { container } = render(<MessageList sessionId="s1" />);
    const list = container.querySelector(".message-list") as HTMLElement;
    installScrollMetrics(list, { scrollHeight: 444, clientHeight: 444, top: 0 });
    fireEvent.scroll(list);

    expect(screen.queryByRole("button", { name: /jump to latest/i })).not.toBeInTheDocument();
  });

  it("hides the jump control again once the bottom is reached", () => {
    const { container } = render(<MessageList sessionId="s1" />);
    const list = container.querySelector(".message-list") as HTMLElement;
    const pos = installScrollMetrics(list, { scrollHeight: 1000, clientHeight: 300, top: 120 });
    fireEvent.scroll(list);
    expect(screen.getByRole("button", { name: /jump to latest/i })).toBeInTheDocument();

    pos.top = 700;
    fireEvent.scroll(list);
    expect(screen.queryByRole("button", { name: /jump to latest/i })).not.toBeInTheDocument();
  });
});
