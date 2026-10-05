// apps/vibe/src/features/code/__tests__/CodePanel.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { render, screen, fireEvent } from "@testing-library/react";
import { CodePanel } from "../CodePanel";
import { useCodeStore } from "../store";

// Monaco needs a real DOM/canvas; stub it with a simple textarea.
vi.mock("@monaco-editor/react", () => ({
  default: ({ value, onChange }: { value?: string; onChange?: (v: string) => void }) => (
    <textarea
      data-testid="editor"
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

describe("CodePanel", () => {
  beforeEach(() => {
    vi.mocked(api.listFiles).mockResolvedValue(["src/App.tsx", "src/main.tsx"]);
    vi.mocked(api.readFile).mockResolvedValue({ path: "src/App.tsx", content: "hello" });
    vi.mocked(api.writeFile).mockResolvedValue({ ok: true });
    useCodeStore.setState({
      files: ["src/App.tsx", "src/main.tsx"],
      selectedFile: "src/App.tsx",
      contents: { "src/App.tsx": "hello" },
    });
  });

  afterEach(() => cleanup());

  it("renders the file tree", () => {
    render(<CodePanel sessionId="s1" />);
    expect(screen.getByText("src/App.tsx")).toBeInTheDocument();
    expect(screen.getByText("src/main.tsx")).toBeInTheDocument();
  });

  it("renders the selected file content in the editor", () => {
    render(<CodePanel sessionId="s1" />);
    expect(screen.getByTestId("editor")).toHaveValue("hello");
  });

  it("renders file entries as buttons with aria-pressed", () => {
    render(<CodePanel sessionId="s1" />);
    const entry = screen.getByRole("button", { name: /src\/App\.tsx/ });
    expect(entry).toHaveAttribute("aria-pressed", "true");
    const other = screen.getByRole("button", { name: /src\/main\.tsx/ });
    expect(other).toHaveAttribute("aria-pressed", "false");
  });

  it("shows a save indicator while saving", async () => {
    let resolveSave: () => void;
    vi.mocked(api.writeFile).mockImplementationOnce(
      () =>
        new Promise<{ ok: true }>((res) => {
          resolveSave = () => res({ ok: true });
        })
    );
    render(<CodePanel sessionId="s1" />);
    fireEvent.change(screen.getByTestId("editor"), { target: { value: "changed" } });
    expect(await screen.findByText("Saving...")).toBeInTheDocument();
    resolveSave!();
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });
});
