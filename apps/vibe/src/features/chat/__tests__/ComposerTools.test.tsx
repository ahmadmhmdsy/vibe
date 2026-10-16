// apps/vibe/src/features/chat/__tests__/ComposerTools.test.tsx
// Behaviour of the composer toolbar, the template library, and the slash menu.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, within } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    sendMessage: vi.fn().mockResolvedValue({ content: "ok", aborted: false }),
    abortSession: vi.fn().mockResolvedValue({ aborted: true }),
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

import { api } from "../../../lib/api";
import { Composer } from "../Composer";
import { useChatStore } from "../store";
import { TEMPLATES } from "../templates";

/** Type into the composer with the caret at the end, the way real typing does.
 * The slash matcher reads selectionStart, so the test has to set it too. */
function type(textbox: HTMLTextAreaElement, value: string) {
  fireEvent.change(textbox, {
    target: { value, selectionStart: value.length, selectionEnd: value.length },
  });
}

function template(id: string) {
  const found = TEMPLATES.find((t) => t.id === id);
  if (!found) throw new Error(`missing template ${id}`);
  return found;
}

afterEach(() => {
  cleanup();
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

describe("composer toolbar", () => {
  it("groups every control in a named toolbar and keeps them focusable", () => {
    render(<Composer sessionId="s1" />);
    const toolbar = screen.getByRole("toolbar", { name: "Composer tools" });
    const reference = within(toolbar).getByRole("button", { name: "Reference a file" });
    const templates = within(toolbar).getByRole("button", { name: "Prompt templates" });
    const plan = within(toolbar).getByRole("radio", { name: "Plan" });
    const act = within(toolbar).getByRole("radio", { name: "Act" });
    const model = within(toolbar).getByLabelText("Model");

    for (const control of [reference, templates, plan, act, model]) {
      expect(control).toBeInTheDocument();
      expect(control).not.toHaveAttribute("tabindex", "-1");
    }
    // Act is the default: the agent changes files unless asked to plan first.
    expect(act).toHaveAttribute("aria-checked", "true");
    expect(plan).toHaveAttribute("aria-checked", "false");
  });

  it("inserts a path reference at the caret", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "Look at ");
    fireEvent.click(screen.getByRole("button", { name: "Reference a file" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Reference a file path/i }));
    expect(textbox).toHaveValue("Look at `path/to/file.tsx`");
  });
});

describe("prompt templates", () => {
  it("puts a template's exact body in the composer", () => {
    render(<Composer sessionId="s1" />);
    const crud = template("crud-list");
    fireEvent.click(screen.getByRole("button", { name: "Prompt templates" }));
    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(crud.label, "i") }));
    expect(screen.getByRole("textbox")).toHaveValue(crud.prompt);
  });

  it("appends instead of discarding a draft the user already typed", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "make it blue");
    const crud = template("crud-list");
    fireEvent.click(screen.getByRole("button", { name: "Prompt templates" }));
    fireEvent.click(screen.getByRole("menuitem", { name: new RegExp(crud.label, "i") }));
    expect(textbox).toHaveValue(`make it blue\n\n${crud.prompt}`);
  });
});

describe("slash commands", () => {
  it("opens on / and filters as the user keeps typing", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "/");
    const list = screen.getByRole("listbox", { name: "Slash commands" });
    expect(within(list).getAllByRole("option").length).toBeGreaterThan(1);

    type(textbox, "/crud");
    // Scope to the listbox: the model picker contributes its own <option>s.
    const filtered = within(screen.getByRole("listbox", { name: "Slash commands" })).getAllByRole(
      "option"
    );
    expect(filtered).toHaveLength(1);
    expect(filtered[0]).toHaveTextContent("CRUD list app");
  });

  it("accepts the highlighted command with ArrowDown and Enter", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    const crud = template("crud-list");
    type(textbox, "/crud");
    fireEvent.keyDown(textbox, { key: "ArrowDown" });
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(textbox).toHaveValue(crud.prompt);
    // Enter drove the menu, not the send action.
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("dismisses on Escape and leaves the typed text untouched", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "/dash");
    expect(screen.getByRole("listbox", { name: "Slash commands" })).toBeInTheDocument();
    fireEvent.keyDown(textbox, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(textbox).toHaveValue("/dash");
  });

  it("does not open for a slash inside a URL", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "see https://example.com");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});

describe("keyboard contract", () => {
  it("sends on Enter", async () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "hello");
    fireEvent.keyDown(textbox, { key: "Enter" });
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("s1", "hello", []));
  });

  it("does not send on Shift+Enter", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "hello");
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("sends on Ctrl+Enter", async () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "hello");
    fireEvent.keyDown(textbox, { key: "Enter", ctrlKey: true });
    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("s1", "hello", []));
  });

  it("does not send while an IME composition is in progress", () => {
    render(<Composer sessionId="s1" />);
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "日本語");
    fireEvent.keyDown(textbox, { key: "Enter", isComposing: true });
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("prefixes the outgoing message when Plan is selected", async () => {
    render(<Composer sessionId="s1" />);
    fireEvent.click(screen.getByRole("radio", { name: "Plan" }));
    const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
    type(textbox, "add a settings page");
    fireEvent.keyDown(textbox, { key: "Enter" });
    await waitFor(() =>
      expect(api.sendMessage).toHaveBeenCalledWith(
        "s1",
        expect.stringMatching(/wait for my confirmation[\s\S]*add a settings page/),
        []
      )
    );
  });
});
