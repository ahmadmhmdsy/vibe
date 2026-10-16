// apps/vibe/src/features/settings/__tests__/SystemPrompt.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    getCatalog: vi.fn().mockResolvedValue([]),
    listProviders: vi.fn().mockResolvedValue([]),
    getSettings: vi.fn(),
    setSystemPrompt: vi.fn(),
  },
}));

import { api } from "../../../lib/api";
import { SettingsPanel } from "../SettingsPanel";
import { useSettingsStore } from "../store";

const defaults = {
  configured: "",
  effective: "You are a helpful agent.",
  default: "You are a helpful agent.",
  source: "default" as const,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getCatalog).mockResolvedValue([]);
  vi.mocked(api.listProviders).mockResolvedValue([]);
  vi.mocked(api.getSettings).mockResolvedValue({ system_prompt: { ...defaults } });
  vi.mocked(api.setSystemPrompt).mockResolvedValue({ system_prompt: { ...defaults } });
});

afterEach(() => {
  cleanup();
  useSettingsStore.setState({ providers: [] });
});

/** The prompt now lives behind a tab, so a test has to open it the way a user
 *  does before any role query can see the controls inside. */
async function loadPromptField(): Promise<HTMLTextAreaElement> {
  render(<SettingsPanel />);
  fireEvent.click(await screen.findByRole("tab", { name: "System prompt" }));
  // The tab panel itself is *named* "System prompt" via aria-labelledby, so a
  // label query would match two elements; ask for the textbox by role.
  return (await screen.findByRole("textbox", {
    name: "System prompt",
  })) as HTMLTextAreaElement;
}

describe("SettingsPanel system prompt", () => {
  it("pre-fills the effective prompt and names the built-in default", async () => {
    const box = await loadPromptField();

    expect(box.value).toBe("You are a helpful agent.");
    expect(box.disabled).toBe(false);
    expect(screen.getByTestId("system-prompt-source")).toHaveTextContent(/built-in default/i);
    // The fallback is visible next to what is in effect, not instead of it.
    expect(screen.getByTestId("system-prompt-default")).toHaveTextContent(
      "You are a helpful agent."
    );
  });

  it("saves what the user typed and reports where it now comes from", async () => {
    const box = await loadPromptField();
    vi.mocked(api.setSystemPrompt).mockResolvedValue({
      system_prompt: { ...defaults, effective: "Be terse.", source: "file" },
    });

    fireEvent.change(box, { target: { value: "Be terse." } });
    fireEvent.click(screen.getByRole("button", { name: /save prompt/i }));

    await waitFor(() => expect(api.setSystemPrompt).toHaveBeenCalledWith("Be terse."));
    await waitFor(() =>
      expect(screen.getByTestId("system-prompt-source")).toHaveTextContent(/saved on this machine/i)
    );
  });

  it("disables the field and explains itself when the environment wins", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      system_prompt: {
        ...defaults,
        configured: "From the env",
        effective: "From the env",
        source: "env",
      },
    });
    const box = await loadPromptField();

    expect(box.value).toBe("From the env");
    expect(box.disabled).toBe(true);
    expect(screen.getByTestId("system-prompt-source")).toHaveTextContent(/VIBE_SYSTEM_PROMPT/);
    expect(screen.getByRole("button", { name: /save prompt/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /reset to default/i })).toBeDisabled();
  });

  it("shows a failed save instead of an empty success", async () => {
    const box = await loadPromptField();
    vi.mocked(api.setSystemPrompt).mockRejectedValue(new Error("disk is read-only"));

    fireEvent.change(box, { target: { value: "Be terse." } });
    fireEvent.click(screen.getByRole("button", { name: /save prompt/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("disk is read-only");
    // Nothing was stored, so the typed text is still there to retry with.
    expect(
      (screen.getByRole("textbox", { name: "System prompt" }) as HTMLTextAreaElement).value
    ).toBe("Be terse.");
  });

  it("resets to the default by saving an empty prompt", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      system_prompt: { ...defaults, effective: "Be terse.", source: "file" },
    });

    await loadPromptField();
    fireEvent.click(screen.getByRole("button", { name: /reset to default/i }));

    await waitFor(() => expect(api.setSystemPrompt).toHaveBeenCalledWith(""));
    await waitFor(() =>
      expect(screen.getByTestId("system-prompt-source")).toHaveTextContent(/built-in default/i)
    );
  });
});
