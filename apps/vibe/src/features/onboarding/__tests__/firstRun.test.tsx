// apps/vibe/src/features/onboarding/__tests__/firstRun.test.tsx
// R5-T4: a first run explains itself. The states that matter are "nothing is
// configured, so say so" and "something is configured, so get out of the way",
// plus the one interaction the panel exists for: an example fills the composer.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    listSessions: vi.fn().mockResolvedValue([]),
    getCatalog: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue({
      id: "s1",
      title: "Test session",
      model: { provider_id: "openai", model_id: "gpt-4o" },
    }),
    createSession: vi.fn().mockResolvedValue({ id: "s1" }),
    renameSession: vi.fn().mockResolvedValue(undefined),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    setSessionModel: vi.fn().mockResolvedValue(undefined),
    listProviders: vi.fn().mockResolvedValue([]),
    listApprovals: vi.fn().mockResolvedValue([]),
    approve: vi.fn().mockResolvedValue(undefined),
    deny: vi.fn().mockResolvedValue(undefined),
    getUsage: vi.fn().mockResolvedValue({ steps: 0 }),
    getMessages: vi.fn().mockResolvedValue({ messages: [], total: 0 }),
    sendMessage: vi.fn().mockResolvedValue(undefined),
    abortSession: vi.fn().mockResolvedValue(undefined),
    listFiles: vi.fn().mockResolvedValue([]),
    readFile: vi.fn().mockResolvedValue({ path: "a.tsx", content: "" }),
    writeFile: vi.fn().mockResolvedValue(undefined),
    runPreview: vi.fn().mockResolvedValue({ url: "http://localhost:5173" }),
    stopPreview: vi.fn().mockResolvedValue(undefined),
    getPreview: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock("../../../lib/sse", () => ({
  SSEClient: class {
    connect() {}
    disconnect() {}
  },
}));

import App from "../../../App";
import { api, type ProviderInfo } from "../../../lib/api";
import { FirstRun } from "../FirstRun";
import { EXAMPLE_PROMPTS } from "../examples";
import { hasConfiguredProvider, shouldShowFirstRun, useFirstRunStore } from "../store";
import { useSessionsStore } from "../../sessions/store";
import { useChatStore } from "../../chat/store";

const builtin = (key_configured: boolean): ProviderInfo => ({
  id: "openai",
  name: "OpenAI",
  capabilities: { tool_support: true, vision: true },
  models: [{ id: "gpt-4o", name: "GPT-4o" }],
  key_configured,
});

const custom = (models: { id: string; name: string }[]): ProviderInfo => ({
  id: "ollama",
  name: "Ollama",
  capabilities: { tool_support: true, vision: false },
  models,
  key_configured: false,
});

/** Render the panel in the state the app would: the catalog has loaded. */
function withProviders(providers: ProviderInfo[]) {
  useFirstRunStore.setState({ providers, loaded: true });
}

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
  useChatStore.setState({ timelineBySession: {}, pendingDraftBySession: {} });
  useFirstRunStore.setState({ providers: [], loaded: false });
  vi.clearAllMocks();
});

describe("hasConfiguredProvider", () => {
  it("is false when a built-in provider has no key", () => {
    expect(hasConfiguredProvider([builtin(false)])).toBe(false);
  });

  it("is true once the key is configured", () => {
    expect(hasConfiguredProvider([builtin(true)])).toBe(true);
  });

  it("counts a keyless custom provider that has models, because local endpoints need no key", () => {
    expect(
      hasConfiguredProvider([builtin(false), custom([{ id: "llama3", name: "Llama 3" }])])
    ).toBe(true);
  });

  it("does not count a half-added custom provider with no models", () => {
    expect(hasConfiguredProvider([custom([])])).toBe(false);
  });
});

describe("shouldShowFirstRun", () => {
  it("stays hidden until the catalog has loaded", () => {
    // A fetch that has not finished, or failed, is not evidence of anything.
    expect(shouldShowFirstRun([builtin(false)], false)).toBe(false);
  });

  it("shows when the catalog loaded and nothing is configured", () => {
    expect(shouldShowFirstRun([builtin(false)], true)).toBe(true);
  });

  it("hides once a provider is configured", () => {
    expect(shouldShowFirstRun([builtin(true)], true)).toBe(false);
  });

  it("stays hidden on an empty catalog", () => {
    expect(shouldShowFirstRun([], true)).toBe(false);
  });
});

describe("FirstRun", () => {
  it("explains the product, the blocker, and the shortcut this keyboard has", () => {
    withProviders([builtin(false)]);
    render(<FirstRun onOpenSettings={() => {}} onUseExample={() => {}} />);

    expect(screen.getByRole("heading", { name: /add a provider key/i })).toBeInTheDocument();
    expect(screen.getByText(/writes the files/i)).toBeInTheDocument();
    // The three steps are the whole answer to "what do I do now".
    expect(screen.getByText(/describe the app you want in the composer/i)).toBeInTheDocument();
    expect(screen.getByText(/watch the agent build, run, and preview it/i)).toBeInTheDocument();
    // Assert the words and the key punctuation without regex escape gymnastics.
    expect(screen.getByText(/or press/)).toHaveTextContent("+,");
  });

  it("offers exactly one primary action and opens the provider panel from it", () => {
    withProviders([builtin(false)]);
    const onOpenSettings = vi.fn();
    const onUseExample = vi.fn();
    render(<FirstRun onOpenSettings={onOpenSettings} onUseExample={onUseExample} />);

    const primary = screen.getByRole("button", { name: /add a provider key/i });
    expect(primary).toHaveClass("btn-primary");
    fireEvent.click(primary);

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
    // One action means one: no other button may reach Settings, and nothing is
    // sent by a click on this panel.
    expect(onUseExample).not.toHaveBeenCalled();
  });

  it("offers concrete example prompts that hand their exact text to the caller", () => {
    withProviders([builtin(false)]);
    const onUseExample = vi.fn();
    render(<FirstRun onOpenSettings={() => {}} onUseExample={onUseExample} />);

    // Every example begins with an imperative verb, which is what keeps them
    // reading as prompts rather than as menu items.
    const examples = screen.getAllByRole("button", { name: /^(build|make) /i });
    expect(examples).toHaveLength(EXAMPLE_PROMPTS.length);
    expect(EXAMPLE_PROMPTS.length).toBeGreaterThanOrEqual(3);

    fireEvent.click(examples[0]);
    expect(onUseExample).toHaveBeenCalledWith(EXAMPLE_PROMPTS[0]);
  });

  it("says a key is missing when a provider exists without one", () => {
    withProviders([builtin(false)]);
    render(<FirstRun onOpenSettings={() => {}} onUseExample={() => {}} />);

    expect(screen.getByText(/none has a key configured/i)).toBeInTheDocument();
    expect(screen.queryByText(/catalog came back empty/i)).not.toBeInTheDocument();
  });

  it("says no provider is reachable when the catalog came back empty", () => {
    withProviders([]);
    render(<FirstRun onOpenSettings={() => {}} onUseExample={() => {}} />);

    expect(
      screen.getByRole("heading", { name: /no model provider is reachable/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/catalog came back empty/i)).toBeInTheDocument();
    expect(screen.queryByText(/none has a key configured/i)).not.toBeInTheDocument();
  });
});

describe("the app first run", () => {
  it("replaces the empty chat, then fills the composer when an example is clicked", async () => {
    vi.mocked(api.getCatalog).mockResolvedValue([builtin(false)]);
    render(<App />);

    expect(await screen.findByRole("heading", { name: /add a provider key/i })).toBeInTheDocument();
    expect(screen.queryByText(/no session selected/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /pomodoro/i }));

    await waitFor(() => expect(api.createSession).toHaveBeenCalledTimes(1));
    const composer = await screen.findByRole("textbox");
    await waitFor(() => expect(composer).toHaveValue(EXAMPLE_PROMPTS[0]));
  });

  it("disappears once a provider is configured", async () => {
    vi.mocked(api.getCatalog).mockResolvedValue([builtin(true)]);
    render(<App />);

    await waitFor(() => expect(api.getCatalog).toHaveBeenCalled());
    expect(await screen.findByText(/no session selected/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /add a provider key/i })).not.toBeInTheDocument();
  });
});
