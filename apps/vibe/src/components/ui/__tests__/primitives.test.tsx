// components/ui/__tests__/primitives.test.tsx
//
// The primitives carry the accessibility contract for the whole app: a roving
// tabindex, a real separator, a tree that reports its own structure. Those are
// exactly the behaviours that break silently, so they are pinned here rather
// than inferred from a screenshot.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Badge } from "../Badge";
import { StatusDot } from "../StatusDot";
import { Kbd } from "../Kbd";
import { Skeleton } from "../Skeleton";
import { SearchField } from "../SearchField";
import { ScrollArea } from "../ScrollArea";
import { Tabs, TabPanel } from "../Tabs";
import { Splitter } from "../Splitter";
import { Tree, type TreeNode } from "../Tree";
import { IconButton } from "../IconButton";
import { EmptyState } from "../EmptyState";
import { Icon } from "../../icons/Icon";

afterEach(cleanup);

describe("Badge", () => {
  it("defaults to the neutral tone and accepts an explicit one", () => {
    const { container } = render(<Badge>Local</Badge>);
    expect(container.querySelector(".badge")?.className).toContain("badge-neutral");

    cleanup();
    const second = render(<Badge tone="success">Ready</Badge>);
    expect(second.container.querySelector(".badge")?.className).toContain("badge-success");
  });
});

describe("StatusDot", () => {
  it("always renders its label, so colour is never the only signal", () => {
    render(<StatusDot status="error" label="Build failed" />);

    // Visually hidden, but present for assistive technology.
    expect(screen.getByText("Build failed")).toBeTruthy();
    expect(document.querySelector(".status-dot")?.getAttribute("data-status")).toBe("error");
  });

  it("shows the label inline when asked", () => {
    render(<StatusDot status="ok" label="Running" showLabel />);

    expect(screen.getByText("Running").className).toContain("status-dot-label");
  });
});

describe("Kbd", () => {
  it("renders one kbd element per key", () => {
    const { container } = render(<Kbd keys={["Ctrl", "K"]} />);

    expect(Array.from(container.querySelectorAll("kbd")).map((node) => node.textContent)).toEqual([
      "Ctrl",
      "K",
    ]);
  });
});

describe("Skeleton", () => {
  it("is hidden from assistive technology", () => {
    const { container } = render(<Skeleton width={120} height={16} />);
    const node = container.querySelector(".skeleton");

    expect(node?.getAttribute("aria-hidden")).toBe("true");
    expect(node?.getAttribute("style")).toContain("width: 120px");
  });
});

describe("SearchField", () => {
  it("associates its label with the input", () => {
    render(<SearchField label="Search sessions" value="" onValueChange={() => {}} />);

    expect(screen.getByLabelText("Search sessions")).toBeTruthy();
  });

  it("reports every keystroke and clears through a named button", () => {
    const onValueChange = vi.fn();
    const { rerender } = render(
      <SearchField label="Search sessions" value="" onValueChange={onValueChange} />
    );

    fireEvent.change(screen.getByLabelText("Search sessions"), { target: { value: "todo" } });
    expect(onValueChange).toHaveBeenCalledWith("todo");

    // The clear button only exists once there is something to clear.
    expect(screen.queryByRole("button")).toBeNull();

    rerender(<SearchField label="Search sessions" value="todo" onValueChange={onValueChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Clear search sessions" }));
    expect(onValueChange).toHaveBeenLastCalledWith("");
  });
});

describe("ScrollArea", () => {
  it("is a labelled region only when it has a name", () => {
    const named = render(
      <ScrollArea label="File contents">
        <p>body</p>
      </ScrollArea>
    );
    const region = named.getByRole("region", { name: "File contents" });
    expect(region.getAttribute("tabindex")).toBe("0");

    cleanup();
    const unnamed = render(
      <ScrollArea>
        <p>body</p>
      </ScrollArea>
    );
    expect(unnamed.container.querySelector(".scroll-region")?.getAttribute("role")).toBeNull();
  });
});

describe("Tabs", () => {
  const items = [
    { id: "preview", label: "Preview" },
    { id: "code", label: "Code" },
    { id: "diagnostics", label: "Diagnostics", disabled: true },
  ];

  it("is a named tablist with one tab stop, not one per tab", () => {
    render(<Tabs items={items} value="preview" onChange={() => {}} label="Panels" />);

    expect(screen.getByRole("tablist", { name: "Panels" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Preview" }).getAttribute("tabindex")).toBe("0");
    expect(screen.getByRole("tab", { name: "Code" }).getAttribute("tabindex")).toBe("-1");
    expect(screen.getByRole("tab", { name: "Preview" }).getAttribute("aria-selected")).toBe("true");
  });

  it("wires each tab to its panel by id", () => {
    render(
      <Tabs items={items} value="preview" onChange={() => {}} label="Panels" idPrefix="side" />
    );

    expect(screen.getByRole("tab", { name: "Preview" }).getAttribute("aria-controls")).toBe(
      "side-panel-preview"
    );
    expect(screen.getByRole("tab", { name: "Preview" }).id).toBe("side-tab-preview");
  });

  it("moves with the arrow keys, wraps, and skips a disabled tab", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <Tabs items={items} value="preview" onChange={onChange} label="Panels" />
    );

    const list = screen.getByRole("tablist", { name: "Panels" });
    fireEvent.keyDown(list, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith("code");

    // The list is controlled — the shell owns `value` — so a wrap is only
    // observable once the new value has been handed back down.
    rerender(<Tabs items={items} value="code" onChange={onChange} label="Panels" />);
    fireEvent.keyDown(list, { key: "ArrowRight" });
    // Past the disabled Diagnostics tab, wrapping to the first enabled one.
    expect(onChange).toHaveBeenLastCalledWith("preview");

    rerender(<Tabs items={items} value="preview" onChange={onChange} label="Panels" />);
    fireEvent.keyDown(list, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenLastCalledWith("code");
  });

  it("jumps to the first and last enabled tab with Home and End", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <Tabs items={items} value="preview" onChange={onChange} label="Panels" />
    );

    const list = screen.getByRole("tablist", { name: "Panels" });
    fireEvent.keyDown(list, { key: "End" });
    // The last *enabled* tab, not the disabled Diagnostics entry.
    expect(onChange).toHaveBeenLastCalledWith("code");

    rerender(<Tabs items={items} value="code" onChange={onChange} label="Panels" />);
    fireEvent.keyDown(list, { key: "End" });
    // Already on the last enabled tab, so there is nothing to change.
    expect(onChange).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(list, { key: "Home" });
    expect(onChange).toHaveBeenLastCalledWith("preview");
  });

  it("activates a tab on click", () => {
    const onChange = vi.fn();
    render(<Tabs items={items} value="preview" onChange={onChange} label="Panels" />);

    fireEvent.click(screen.getByRole("tab", { name: "Code" }));
    expect(onChange).toHaveBeenCalledWith("code");
  });

  it("keeps an inactive panel mounted but hidden, and named by its tab", () => {
    render(
      <div>
        <Tabs items={items} value="preview" onChange={() => {}} label="Panels" idPrefix="side" />
        <TabPanel id="preview" idPrefix="side" active>
          <p>preview body</p>
        </TabPanel>
        <TabPanel id="code" idPrefix="side" active={false}>
          <p>code body</p>
        </TabPanel>
      </div>
    );

    const active = screen.getByRole("tabpanel", { name: "Preview" });
    expect(active.hasAttribute("hidden")).toBe(false);

    // Hidden from the accessibility tree, not merely painted over — that is
    // what the `hidden` attribute buys us, and it is why a screen reader
    // never reads the Code panel while the Preview tab is selected. A hidden
    // element has no computed name, so it is identified by its id here.
    expect(screen.queryByRole("tabpanel", { name: "Code" })).toBeNull();

    const inactive = document.getElementById("side-panel-code");
    expect(inactive?.hasAttribute("hidden")).toBe(true);
    expect(inactive?.getAttribute("aria-labelledby")).toBe("side-tab-code");

    // Still in the DOM, so an iframe or editor model survives the switch.
    expect(screen.getByText("code body")).toBeTruthy();
  });
});

describe("Splitter", () => {
  const setup = (overrides: Partial<Parameters<typeof Splitter>[0]> = {}) => {
    const onChange = vi.fn();
    const props = {
      value: 400,
      min: 320,
      max: 560,
      onChange,
      label: "Resize the preview panel",
      ...overrides,
    };
    render(<Splitter {...props} />);
    return {
      onChange,
      handle: screen.getByRole("separator", { name: "Resize the preview panel" }),
    };
  };

  it("exposes itself as a labelled separator with its range", () => {
    const { handle } = setup();

    expect(handle.getAttribute("aria-orientation")).toBe("vertical");
    expect(handle.getAttribute("aria-valuenow")).toBe("400");
    expect(handle.getAttribute("aria-valuemin")).toBe("320");
    expect(handle.getAttribute("aria-valuemax")).toBe("560");
    expect(handle.getAttribute("tabindex")).toBe("0");
  });

  it("grows with the arrow key that points away from the controlled pane", () => {
    const { onChange, handle } = setup();

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith(416);

    fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenLastCalledWith(384);
  });

  it("reverses the arrow direction when the pane sits before it", () => {
    const { onChange, handle } = setup({ invert: true });

    fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenCalledWith(416);

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith(384);
  });

  it("takes a four-times step with Shift held", () => {
    const { onChange, handle } = setup();

    fireEvent.keyDown(handle, { key: "ArrowRight", shiftKey: true });
    expect(onChange).toHaveBeenCalledWith(464);
  });

  it("jumps to the limits with Home and End", () => {
    const { onChange, handle } = setup();

    fireEvent.keyDown(handle, { key: "Home" });
    expect(onChange).toHaveBeenLastCalledWith(320);

    fireEvent.keyDown(handle, { key: "End" });
    expect(onChange).toHaveBeenLastCalledWith(560);
  });

  it("clamps instead of running past the limits", () => {
    const { onChange, handle } = setup({ value: 552 });

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith(560);
  });

  it("restores the default on double-click when one is given", () => {
    const { onChange, handle } = setup({ value: 500, defaultValue: 420 });

    fireEvent.doubleClick(handle);
    expect(onChange).toHaveBeenCalledWith(420);
  });

  it("ignores the keys it does not own", () => {
    const { onChange, handle } = setup();

    fireEvent.keyDown(handle, { key: "a" });
    fireEvent.keyDown(handle, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("Tree", () => {
  const nodes: TreeNode[] = [
    {
      id: "src",
      name: "src",
      children: [
        { id: "src/App.tsx", name: "App.tsx" },
        { id: "src/main.tsx", name: "main.tsx" },
      ],
    },
    { id: "package.json", name: "package.json" },
  ];

  const setup = (overrides: Partial<Parameters<typeof Tree>[0]> = {}) => {
    const onSelect = vi.fn();
    const onToggle = vi.fn();
    const props = {
      nodes,
      onSelect,
      onToggle,
      expandedIds: new Set<string>(),
      label: "Project files",
      ...overrides,
    };
    render(<Tree {...props} />);
    return { onSelect, onToggle };
  };

  it("is a named tree that reports its own structure", () => {
    setup({ expandedIds: new Set(["src"]) });

    const tree = screen.getByRole("tree", { name: "Project files" });
    expect(tree).toBeTruthy();

    const folder = screen.getByRole("treeitem", { name: /src/ });
    expect(folder.getAttribute("aria-level")).toBe("1");
    expect(folder.getAttribute("aria-expanded")).toBe("true");
    expect(folder.getAttribute("aria-setsize")).toBe("2");
    expect(folder.getAttribute("aria-posinset")).toBe("1");

    const child = screen.getByRole("treeitem", { name: /App.tsx/ });
    expect(child.getAttribute("aria-level")).toBe("2");
    // A leaf has no expanded state at all.
    expect(child.getAttribute("aria-expanded")).toBeNull();
  });

  it("hides the children of a collapsed folder", () => {
    setup();

    expect(screen.queryByRole("treeitem", { name: /App.tsx/ })).toBeNull();
  });

  it("keeps a single tab stop and moves it with the arrow keys", () => {
    setup();

    const folder = screen.getByRole("treeitem", { name: /src/ });
    const leaf = screen.getByRole("treeitem", { name: /package.json/ });

    expect(folder.getAttribute("tabindex")).toBe("0");
    expect(leaf.getAttribute("tabindex")).toBe("-1");

    fireEvent.keyDown(folder, { key: "ArrowDown" });
    expect(document.activeElement).toBe(leaf);
  });

  it("expands a collapsed folder with ArrowRight and collapses it with ArrowLeft", () => {
    const { onToggle } = setup();

    fireEvent.keyDown(screen.getByRole("treeitem", { name: /src/ }), { key: "ArrowRight" });
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ id: "src" }));
  });

  it("collapses an expanded folder with ArrowLeft instead of leaving it", () => {
    const { onToggle } = setup({ expandedIds: new Set(["src"]) });

    fireEvent.keyDown(screen.getByRole("treeitem", { name: /src/ }), { key: "ArrowLeft" });
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ id: "src" }));
  });

  it("walks back to the parent from a leaf", () => {
    setup({ expandedIds: new Set(["src"]) });

    const child = screen.getByRole("treeitem", { name: /App.tsx/ });
    fireEvent.keyDown(child, { key: "ArrowLeft" });

    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: /src/ }));
  });

  it("selects with Enter and with Space", () => {
    const { onSelect } = setup();

    const leaf = screen.getByRole("treeitem", { name: /package.json/ });
    fireEvent.keyDown(leaf, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "package.json" }));

    fireEvent.keyDown(leaf, { key: " " });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it("selects on click", () => {
    const { onSelect } = setup();

    fireEvent.click(screen.getByRole("treeitem", { name: /src/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "src" }));
  });

  it("renders nothing when there are no nodes", () => {
    const { container } = render(
      <Tree
        nodes={[]}
        onSelect={() => {}}
        onToggle={() => {}}
        expandedIds={new Set()}
        label="Files"
      />
    );

    expect(container.querySelector(".tree")).toBeNull();
  });
});

describe("IconButton", () => {
  it("takes its accessible name from the label prop", () => {
    render(
      <IconButton label="Toggle the sidebar">
        <Icon name="panelLeft" />
      </IconButton>
    );

    expect(screen.getByRole("button", { name: "Toggle the sidebar" })).toBeTruthy();
  });

  it("does not submit an enclosing form", () => {
    render(
      <IconButton label="Close">
        <Icon name="close" />
      </IconButton>
    );

    expect(screen.getByRole("button", { name: "Close" }).getAttribute("type")).toBe("button");
  });
});

describe("Icon", () => {
  it("is decorative unless it is given a label", () => {
    const { container } = render(<Icon name="settings" />);
    const svg = container.querySelector("svg");

    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.getAttribute("role")).toBeNull();
  });

  it("becomes a named image when it carries meaning", () => {
    render(<Icon name="settings" label="Settings" />);

    expect(screen.getByRole("img", { name: "Settings" })).toBeTruthy();
  });
});

describe("EmptyState", () => {
  it("renders the title at the requested heading level", () => {
    render(<EmptyState title="No sessions yet" body="Describe an app to begin." />);

    expect(screen.getByRole("heading", { level: 2, name: "No sessions yet" })).toBeTruthy();
    expect(screen.getByText("Describe an app to begin.")).toBeTruthy();
  });
});
