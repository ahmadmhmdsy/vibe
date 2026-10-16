// components/ui/__tests__/CommandPalette.test.tsx — render-phase reset + filtering.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { CommandPalette } from "../CommandPalette";

afterEach(cleanup);

const commands = [
  { id: "1", title: "New session", description: "Create a new session", action: vi.fn() },
  { id: "2", title: "Open settings", description: "Open the settings panel", action: vi.fn() },
  { id: "3", title: "Toggle theme", description: "Switch between light and dark", action: vi.fn() },
];

const renderPalette = (props: Partial<Parameters<typeof CommandPalette>[0]> = {}) =>
  render(<CommandPalette open onClose={() => {}} commands={commands} {...props} />);

describe("CommandPalette", () => {
  it("opens with an empty query and the first item selected", () => {
    renderPalette();
    expect(screen.getByLabelText("Search commands")).toHaveValue("");
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("New session");
  });

  it("filters commands as the user types", () => {
    renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.change(input, { target: { value: "settings" } });
    expect(screen.getByRole("option", { name: /open settings/i })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /new session/i })).not.toBeInTheDocument();
  });

  it("resets the query and selection when reopened", () => {
    const { rerender } = renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.change(input, { target: { value: "settings" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    rerender(<CommandPalette open={false} onClose={() => {}} commands={commands} />);
    rerender(<CommandPalette open onClose={() => {}} commands={commands} />);
    expect(screen.getByLabelText("Search commands")).toHaveValue("");
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("New session");
  });

  it("resets the selection to the first match when the query changes", () => {
    renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("Open settings");
    fireEvent.change(input, { target: { value: "toggle" } });
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("Toggle theme");
  });

  it("moves the selection with arrow keys", () => {
    renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("Open settings");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("Toggle theme");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(screen.getByRole("option", { selected: true })).toHaveTextContent("Open settings");
  });

  it("executes the selected command on Enter", () => {
    renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(commands[1].action).toHaveBeenCalledOnce();
  });

  it("shows an empty state when no commands match", () => {
    renderPalette();
    const input = screen.getByLabelText("Search commands");
    fireEvent.change(input, { target: { value: "zzzz" } });
    expect(screen.getByText("No commands found")).toBeInTheDocument();
  });
});
