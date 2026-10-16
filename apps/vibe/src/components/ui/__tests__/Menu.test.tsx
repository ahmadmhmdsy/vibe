// components/ui/__tests__/Menu.test.tsx — keyboard behaviour of the dropdown.
//
// Regression test: the item list used to be rebuilt on every render, which
// re-ran the "focus the first item" effect after each keystroke and pinned
// focus to the first entry, making ArrowDown a no-op.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Menu, type MenuEntry } from "../Menu";

afterEach(cleanup);

function makeEntries(): MenuEntry[] {
  return [
    { id: "rename", label: "Rename", onSelect: vi.fn() },
    { id: "duplicate", label: "Duplicate", onSelect: vi.fn() },
    { id: "delete", label: "Delete", danger: true, onSelect: vi.fn() },
  ];
}

function openMenu(entries: MenuEntry[]) {
  render(<Menu label="Session actions" icon={<span />} entries={entries} />);
  const trigger = screen.getByRole("button", { name: "Session actions" });
  fireEvent.click(trigger);
  return trigger;
}

/** Key events bubble from the focused item up to the popup's handler. */
function press(key: string) {
  const focused = document.activeElement as HTMLElement;
  fireEvent.keyDown(focused, { key });
}

const item = (name: string) => screen.getByRole("menuitem", { name });

describe("Menu", () => {
  it("opens on the first item", () => {
    openMenu(makeEntries());

    expect(item("Rename")).toHaveFocus();
    expect(screen.getByRole("button", { name: "Session actions" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
  });

  it("walks the items with the arrow keys and wraps", () => {
    openMenu(makeEntries());

    press("ArrowDown");
    expect(item("Duplicate")).toHaveFocus();

    press("ArrowDown");
    expect(item("Delete")).toHaveFocus();

    press("ArrowDown");
    expect(item("Rename")).toHaveFocus();

    press("ArrowUp");
    expect(item("Delete")).toHaveFocus();
  });

  it("jumps to the ends with Home and End", () => {
    openMenu(makeEntries());

    press("End");
    expect(item("Delete")).toHaveFocus();

    press("Home");
    expect(item("Rename")).toHaveFocus();
  });

  it("closes on Escape and returns focus to the trigger", () => {
    const trigger = openMenu(makeEntries());

    press("Escape");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("skips disabled entries", () => {
    const entries = makeEntries();
    // Rename, Share (disabled), Duplicate, Delete.
    entries.splice(1, 0, { id: "share", label: "Share", disabled: true, onSelect: vi.fn() });
    openMenu(entries);

    // One press moves past Rename straight to Duplicate: Share is inert.
    press("ArrowDown");

    expect(item("Duplicate")).toHaveFocus();

    press("ArrowUp");

    expect(item("Rename")).toHaveFocus();
  });

  it("runs the selected action and closes", () => {
    const entries = makeEntries();
    openMenu(entries);

    fireEvent.click(item("Duplicate"));

    expect(entries[1] && "onSelect" in entries[1] && entries[1].onSelect).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
