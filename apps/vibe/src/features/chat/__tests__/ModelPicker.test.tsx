// apps/vibe/src/features/chat/__tests__/ModelPicker.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    getCatalog: vi.fn().mockResolvedValue([]),
    getSession: vi.fn().mockResolvedValue({
      id: "s1",
      title: "t",
      model: { provider_id: "openai", model_id: "gpt-4o" },
    }),
    setSessionModel: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

import { api } from "../../../lib/api";
import { ModelPicker } from "../ModelPicker";
import { useChatStore } from "../store";

beforeEach(() => {
  useChatStore.setState({ model: { provider_id: "openai", model_id: "gpt-4o" } });
  vi.clearAllMocks();
  vi.mocked(api.getCatalog).mockResolvedValue([
    {
      id: "custom",
      name: "Custom Co",
      capabilities: { tool_support: true, vision: false },
      models: [{ id: "org/model-instruct", name: "Slashed model" }],
      key_configured: true,
    },
  ]);
  vi.mocked(api.getSession).mockResolvedValue({
    id: "s1",
    title: "t",
    model: { provider_id: "openai", model_id: "gpt-4o" },
  });
});

afterEach(cleanup);

describe("ModelPicker", () => {
  it("keeps a model id that contains a slash intact", async () => {
    // Splitting the option value on "/" turned "custom/org/model-instruct"
    // into provider_id "custom", model_id "org" — the wrong model entirely.
    render(<ModelPicker sessionId="s1" />);
    await screen.findByRole("option", { name: "Slashed model" });

    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "custom/org/model-instruct" },
    });

    expect(useChatStore.getState().model).toEqual({
      provider_id: "custom",
      model_id: "org/model-instruct",
    });
    await waitFor(() =>
      expect(api.setSessionModel).toHaveBeenCalledWith("s1", {
        provider_id: "custom",
        model_id: "org/model-instruct",
      })
    );
  });

  it("reflects the active session's stored model", async () => {
    vi.mocked(api.getSession).mockResolvedValue({
      id: "s1",
      title: "t",
      model: { provider_id: "custom", model_id: "org/model-instruct" },
    });
    render(<ModelPicker sessionId="s1" />);
    await waitFor(() =>
      expect(useChatStore.getState().model).toEqual({
        provider_id: "custom",
        model_id: "org/model-instruct",
      })
    );
  });
});
