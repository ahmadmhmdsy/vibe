// apps/vibe/src/features/settings/__tests__/SettingsPanel.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    getCatalog: vi.fn().mockResolvedValue([]),
    listProviders: vi.fn().mockResolvedValue([]),
    updateProvider: vi.fn().mockResolvedValue({ ok: true }),
    createProvider: vi.fn().mockResolvedValue({ ok: true }),
    deleteProvider: vi.fn().mockResolvedValue({ ok: true }),
    // The panel also renders the system-prompt tab (BE-19), so it reads this on
    // mount. Those tests live in SystemPrompt.test.tsx.
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

import { api, type CustomProvider, type ProviderInfo } from "../../../lib/api";
import { SettingsPanel } from "../SettingsPanel";
import { useSettingsStore } from "../store";
import { ToastProvider } from "../../../components/ui";

const custom: CustomProvider = {
  id: "p1",
  name: "Custom Co",
  baseUrl: "http://localhost:1234/v1",
  key_configured: true,
  models: [{ id: "org/model", name: "Slashed", protocol: "openai-chat" }],
};

const builtin: ProviderInfo = {
  id: "openai",
  name: "OpenAI",
  capabilities: { tool_support: true, vision: true },
  models: [{ id: "gpt-4o", name: "GPT-4o" }],
  key_configured: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getCatalog).mockResolvedValue([]);
  vi.mocked(api.listProviders).mockResolvedValue([custom]);
  vi.mocked(api.updateProvider).mockResolvedValue(custom);
  vi.mocked(api.getSettings).mockResolvedValue({
    system_prompt: {
      configured: "",
      effective: "You are a helpful agent.",
      default: "You are a helpful agent.",
      source: "default",
    },
  });
});

afterEach(() => {
  cleanup();
  useSettingsStore.setState({ providers: [] });
});

describe("SettingsPanel providers", () => {
  it("holds the layout with a skeleton while the provider list loads", () => {
    vi.mocked(api.getCatalog).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.listProviders).mockReturnValue(new Promise(() => {}));
    render(<SettingsPanel />);

    expect(screen.getByText(/loading providers/i)).toBeInTheDocument();
  });

  it("shows a retry when the provider list fails, and recovers on retry", async () => {
    vi.mocked(api.getCatalog).mockRejectedValueOnce(new Error("catalog unreachable"));
    render(<SettingsPanel />);

    expect(await screen.findByRole("alert")).toHaveTextContent("catalog unreachable");

    vi.mocked(api.getCatalog).mockResolvedValue([]);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => expect(screen.queryByText(/catalog unreachable/i)).not.toBeInTheDocument());
  });

  it("labels every provider key input and never renders a stored key back", async () => {
    render(<SettingsPanel />);

    const input = (await screen.findByLabelText(/api key for custom co/i)) as HTMLInputElement;
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveValue("");
    expect(input).not.toBeDisabled();
    // The configured state is reported as text, so colour is not the only cue.
    expect(screen.getByText("Key configured")).toBeInTheDocument();
  });

  it("disables the key input for a built-in provider whose key comes from the environment", async () => {
    vi.mocked(api.getCatalog).mockResolvedValue([builtin]);
    render(<SettingsPanel />);

    const input = (await screen.findByLabelText(/api key for openai/i)) as HTMLInputElement;
    expect(input).toBeDisabled();
    expect(input).toHaveAttribute("placeholder", "Set by the server environment");
    expect(screen.getByText("No key")).toBeInTheDocument();
  });

  it("offers no clear action for a provider with no stored key", async () => {
    vi.mocked(api.listProviders).mockResolvedValue([{ ...custom, key_configured: false }]);
    render(<SettingsPanel />);

    expect(await screen.findByLabelText(/api key for custom co/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /clear key/i })).not.toBeInTheDocument();
  });

  it("clears a stored key with an explicit empty apiKey", async () => {
    // apiKey: "" rather than omitting the field is what asks the backend to
    // forget the key; an empty form field must not silently clear it instead.
    render(<SettingsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /clear key/i }));

    await waitFor(() =>
      expect(api.updateProvider).toHaveBeenCalledWith("p1", expect.objectContaining({ apiKey: "" }))
    );
  });

  it("saves a typed key and reports success", async () => {
    render(
      <ToastProvider>
        <SettingsPanel />
      </ToastProvider>
    );

    const input = await screen.findByLabelText(/api key for custom co/i);
    fireEvent.change(input, { target: { value: "sk-test" } });
    fireEvent.click(screen.getByRole("button", { name: /save key/i }));

    await waitFor(() =>
      expect(api.updateProvider).toHaveBeenCalledWith("p1", { apiKey: "sk-test" })
    );
    expect(await screen.findByText("API key saved")).toBeInTheDocument();
    // The draft is cleared, so nothing is left on screen to leak.
    expect(screen.getByLabelText(/api key for custom co/i)).toHaveValue("");
  });

  it("surfaces a failed key save instead of a silent success", async () => {
    vi.mocked(api.updateProvider).mockRejectedValue(new Error("key store is read-only"));
    render(<SettingsPanel />);

    const input = await screen.findByLabelText(/api key for custom co/i);
    fireEvent.change(input, { target: { value: "sk-test" } });
    fireEvent.click(screen.getByRole("button", { name: /save key/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("key store is read-only");
    // Nothing was stored, so the typed key is still there to retry with.
    expect(screen.getByLabelText(/api key for custom co/i)).toHaveValue("sk-test");
  });

  it("moves focus to the first provider control when first-run sends the user here", async () => {
    render(<SettingsPanel focusProviders />);

    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveFocus());
  });

  it("requires a name and a base URL before saving a provider", async () => {
    render(<SettingsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /add provider/i }));
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/name and base url are required/i);
    expect(api.createProvider).not.toHaveBeenCalled();
  });

  it("deletes a provider only through the confirm dialog", async () => {
    render(<SettingsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /delete custom co/i }));
    fireEvent.click(await screen.findByRole("button", { name: /^delete$/i }));

    await waitFor(() => expect(api.deleteProvider).toHaveBeenCalledWith("p1"));
  });
});

describe("SettingsPanel tabs", () => {
  it("keeps each tab's content reachable and hides the other panel", async () => {
    render(<SettingsPanel />);

    // The providers panel is the one that starts active and exposed.
    expect(screen.getByRole("tabpanel", { name: "Providers" })).toBeInTheDocument();
    expect(screen.queryByRole("tabpanel", { name: "System prompt" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "System prompt" }));

    expect(await screen.findByRole("tabpanel", { name: "System prompt" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save prompt/i })).toBeInTheDocument();
    expect(screen.queryByRole("tabpanel", { name: "Providers" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Providers" }));

    expect(await screen.findByRole("button", { name: /add provider/i })).toBeInTheDocument();
  });
});
