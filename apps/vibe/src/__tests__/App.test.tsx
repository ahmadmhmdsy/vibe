// apps/vibe/src/__tests__/App.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, within } from "@testing-library/react";

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
    // The settings modal renders the system-prompt section (BE-19), so opening
    // it reads this. Its own behaviour is covered in features/settings.
    getSettings: vi.fn().mockResolvedValue({
      system_prompt: {
        configured: "",
        effective: "You are a helpful agent.",
        default: "You are a helpful agent.",
        source: "default",
      },
    }),
    setSystemPrompt: vi.fn(),
  },
}));

vi.mock("../lib/sse", () => ({
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

import App from "../App";
import { api } from "../lib/api";
import { useSessionsStore } from "../features/sessions/store";

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
  localStorage.removeItem("vibe.theme");
  delete document.documentElement.dataset.theme;
  Reflect.deleteProperty(navigator, "platform");
  vi.clearAllMocks();
});

/** Pretend the browser runs on another OS. */
function setPlatform(platform: string) {
  Object.defineProperty(navigator, "platform", { value: platform, configurable: true });
}

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
    // Scoped to the main region: the sidebar header carries the same primary
    // action, and both labels are deliberate — one creates a session from the
    // list, the other from an empty conversation.
    expect(
      within(screen.getByRole("main")).getByRole("button", { name: /new session/i })
    ).toBeInTheDocument();
  });

  it("binds Cmd+N on macOS", async () => {
    setPlatform("MacIntel");
    render(<App />);
    fireEvent.keyDown(document, { key: "n", metaKey: true });
    await waitFor(() => expect(api.createSession).toHaveBeenCalledTimes(1));
  });

  it("does not answer Ctrl+Alt+N on macOS", () => {
    setPlatform("MacIntel");
    render(<App />);
    fireEvent.keyDown(document, { key: "n", ctrlKey: true, altKey: true });
    expect(api.createSession).not.toHaveBeenCalled();
  });

  it("binds Ctrl+Alt+N on Windows/Linux, where Ctrl+N is browser-reserved", async () => {
    setPlatform("Win32");
    render(<App />);

    // The plain browser binding must be left alone.
    fireEvent.keyDown(document, { key: "n", ctrlKey: true });
    expect(api.createSession).not.toHaveBeenCalled();

    fireEvent.keyDown(document, { key: "n", ctrlKey: true, altKey: true });
    await waitFor(() => expect(api.createSession).toHaveBeenCalledTimes(1));
  });

  it("advertises Cmd+N in the palette on macOS", () => {
    setPlatform("MacIntel");
    render(<App />);
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByRole("option", { name: /new session/i })).toHaveTextContent("Cmd N");
  });

  it("advertises Ctrl+Alt+N in the palette off macOS", () => {
    setPlatform("Win32");
    render(<App />);
    fireEvent.keyDown(document, { key: "k", ctrlKey: true });
    expect(screen.getByRole("option", { name: /new session/i })).toHaveTextContent("Ctrl Alt N");
  });

  it("applies the stored theme on first paint", () => {
    // The stored theme was only written by an explicit toggle, so a reload
    // rendered the default theme until the user toggled again.
    localStorage.setItem("vibe.theme", "light");
    render(<App />);
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
