// apps/vibe/src/features/code/__tests__/CodePanel.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup, act } from "@testing-library/react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { CodePanel } from "../CodePanel";
import { useCodeStore } from "../store";

// Monaco needs a real DOM/canvas; stub it with a simple textarea.
vi.mock("@monaco-editor/react", () => ({
  default: ({
    value,
    onChange,
    theme,
  }: {
    value?: string;
    onChange?: (v: string) => void;
    theme?: string;
  }) => (
    <textarea
      data-testid="editor"
      data-theme={theme}
      value={value ?? ""}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

vi.mock("../../../lib/api", () => ({
  api: {
    listFiles: vi.fn(),
    readFile: vi.fn(),
    writeFile: vi.fn(),
  },
}));

import { api } from "../../../lib/api";

const FILES = ["App.tsx", "src/main.tsx", "src/components/Button.tsx"];

/** Waits for the initial file-list load to settle. */
async function flushed() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("CodePanel", () => {
  beforeEach(() => {
    // Call history is cumulative across tests; every assertion on
    // mock.calls.length depends on this reset.
    vi.clearAllMocks();
    vi.mocked(api.listFiles).mockResolvedValue(FILES);
    vi.mocked(api.readFile).mockResolvedValue({ path: "App.tsx", content: "hello" });
    vi.mocked(api.writeFile).mockResolvedValue({ ok: true });
    useCodeStore.setState({
      files: FILES,
      selectedFile: "App.tsx",
      contents: { "App.tsx": "hello" },
    });
  });

  afterEach(() => cleanup());

  it("builds a folder tree from the workspace paths", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    const tree = screen.getByRole("tree", { name: "Workspace files" });

    // Folders group the paths; the leaf is the file's own name, not its path.
    expect(within(tree).getByRole("treeitem", { name: "src" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    expect(within(tree).getByRole("treeitem", { name: "App.tsx" })).toBeInTheDocument();
    expect(within(tree).getByRole("treeitem", { name: "main.tsx" })).toBeInTheDocument();
    // Nested one level deeper than src.
    expect(within(tree).getByRole("treeitem", { name: "components" })).toHaveAttribute(
      "aria-level",
      "2"
    );
    expect(within(tree).getByRole("treeitem", { name: "Button.tsx" })).toHaveAttribute(
      "aria-level",
      "3"
    );
  });

  it("collapses a folder when its row is activated", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    const src = screen.getByRole("treeitem", { name: "src" });
    fireEvent.click(src);
    expect(src).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("treeitem", { name: "main.tsx" })).not.toBeInTheDocument();
  });

  it("selecting a file reads it through the store", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    fireEvent.click(screen.getByRole("treeitem", { name: "main.tsx" }));

    expect(useCodeStore.getState().selectedFile).toBe("src/main.tsx");
    expect(vi.mocked(api.readFile)).toHaveBeenCalledWith("s1", "src/main.tsx");
    expect(screen.getByRole("treeitem", { name: "main.tsx" })).toHaveAttribute(
      "aria-selected",
      "true"
    );
  });

  it("keeps a collapsed folder closed when the file list refreshes", async () => {
    render(<CodePanel sessionId="s1" active={false} />);
    await flushed();
    const src = () => screen.getByRole("treeitem", { name: "src" });
    fireEvent.click(src());
    expect(src()).toHaveAttribute("aria-expanded", "false");

    // A poll (or the refresh action) replaces the file list; it must not
    // override the user's collapse.
    await act(async () => {
      await useCodeStore.getState().loadFiles("s1");
    });
    expect(src()).toHaveAttribute("aria-expanded", "false");
  });

  it("selecting a folder does not open it as a file", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    fireEvent.click(screen.getByRole("treeitem", { name: "src" }));
    expect(useCodeStore.getState().selectedFile).toBe("App.tsx");
  });

  it("renders the selected file content in the editor", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    expect(screen.getByTestId("editor")).toHaveValue("hello");
  });

  it("uses the layout contract for the row", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    // Geometry cannot be asserted in jsdom (no layout engine), so this checks
    // the box chain the CSS depends on: the panel body carries the row
    // direction and the editor wrapper is its last child.
    const body = screen.getByTestId("code-layout");
    expect(body).toHaveClass("panel-body");
    expect(body).toHaveAttribute("data-direction", "row");
    const editor = document.querySelector(".code-editor");
    expect(editor).not.toBeNull();
    expect(body.lastElementChild).toBe(editor);
    expect(document.querySelector(".code-editor-body")).toContainElement(
      screen.getByTestId("editor")
    );
    expect(screen.getByRole("separator", { name: "Resize file tree" })).toBeInTheDocument();
  });

  it("opens the editor in the app's theme", async () => {
    render(<CodePanel sessionId="s1" theme="light" />);
    await flushed();
    expect(screen.getByTestId("editor")).toHaveAttribute("data-theme", "light");
  });

  it("defaults to the dark editor", async () => {
    render(<CodePanel sessionId="s1" />);
    await flushed();
    expect(screen.getByTestId("editor")).toHaveAttribute("data-theme", "vs-dark");
  });

  it("renders the empty state instead of an empty tree when there are no files", async () => {
    vi.mocked(api.listFiles).mockResolvedValue([]);
    useCodeStore.setState({ files: [], selectedFile: null, contents: {} });
    render(<CodePanel sessionId="s1" />);
    await flushed();

    expect(screen.getByText("No files yet")).toBeInTheDocument();
    expect(screen.queryByRole("tree")).not.toBeInTheDocument();
  });

  it("surfaces a file that cannot be read", async () => {
    vi.mocked(api.readFile).mockRejectedValue(new Error("API error: 404"));
    render(<CodePanel sessionId="s1" />);
    expect(await screen.findByText(/API error: 404/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows the save state in the editor header while saving", async () => {
    let resolveSave: () => void;
    vi.mocked(api.writeFile).mockImplementationOnce(
      () =>
        new Promise<{ ok: true }>((res) => {
          resolveSave = () => res({ ok: true });
        })
    );
    render(<CodePanel sessionId="s1" />);
    await flushed();
    fireEvent.change(screen.getByTestId("editor"), { target: { value: "changed" } });
    // The label is visible and also mirrored as visually-hidden text for the
    // dot, so both nodes legitimately carry the word.
    expect(await screen.findAllByText("Saving")).not.toHaveLength(0);
    resolveSave!();
    expect(await screen.findAllByText("Saved")).not.toHaveLength(0);
  });

  it("stops polling the file list while it is not the active panel", async () => {
    vi.useFakeTimers();
    try {
      render(<CodePanel sessionId="s1" active={false} />);
      await vi.advanceTimersByTimeAsync(7000);
      // Only the mount load runs; the 3s poll stays off.
      expect(vi.mocked(api.listFiles).mock.calls.length).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("polls the file list while it is the active panel", async () => {
    vi.useFakeTimers();
    try {
      render(<CodePanel sessionId="s1" active />);
      await vi.advanceTimersByTimeAsync(7000);
      expect(vi.mocked(api.listFiles).mock.calls.length).toBeGreaterThan(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
