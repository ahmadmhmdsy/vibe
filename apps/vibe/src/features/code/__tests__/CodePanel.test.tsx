// apps/vibe/src/features/code/__tests__/CodePanel.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { render, screen } from "@testing-library/react";
import { CodePanel } from "../CodePanel";
import { useCodeStore } from "../store";

// Monaco needs a real DOM/canvas; stub it with a simple textarea.
vi.mock("@monaco-editor/react", () => ({
  default: ({ value, onChange }: { value?: string; onChange?: (v: string) => void }) => (
    <textarea data-testid="editor" value={value ?? ""} onChange={(e) => onChange?.(e.target.value)} />
  ),
}));

describe("CodePanel", () => {
  beforeEach(() => {
    useCodeStore.setState({ files: ["src/App.tsx", "src/main.tsx"], selectedFile: "src/App.tsx", contents: { "src/App.tsx": "hello" } });
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
});
