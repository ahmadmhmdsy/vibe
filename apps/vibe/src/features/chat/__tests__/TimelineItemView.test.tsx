// features/chat/__tests__/TimelineItemView.test.tsx
import { describe, it, expect, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { TimelineItemView } from "../TimelineItemView";
import type { AssistantItem, ToolItem } from "../timeline";

afterEach(cleanup);

const tool = (over: Partial<ToolItem> = {}): ToolItem => ({
  kind: "tool",
  id: "t1",
  seq: 2,
  callId: "c1",
  name: "write_file",
  args: { path: "src/App.tsx" },
  status: "running",
  startedAt: Date.now(),
  ...over,
});

describe("TimelineItemView", () => {
  it("shows the tool, its argument summary, and its status word", () => {
    render(
      <TimelineItemView item={tool({ status: "ok", result: "done", finishedAt: Date.now() })} />
    );
    expect(
      screen.getByRole("button", { name: /write_file src\/App\.tsx done/i })
    ).toBeInTheDocument();
  });

  it("reveals arguments and result when expanded", () => {
    render(<TimelineItemView item={tool({ status: "ok", result: "wrote 3 lines" })} />);
    fireEvent.click(screen.getByRole("button", { name: /write_file/ }));
    expect(screen.getByText("Arguments")).toBeInTheDocument();
    expect(screen.getByText("Result")).toBeInTheDocument();
    expect(screen.getByText(/wrote 3 lines/)).toBeInTheDocument();
  });

  it("renders an assistant fence as a code block", () => {
    const item: AssistantItem = {
      kind: "assistant",
      id: "a1",
      seq: 2,
      content: "Try:\n```ts\nconst a = 1;\n```",
      streaming: false,
    };
    const { container } = render(<TimelineItemView item={item} />);
    expect(container.querySelector(".code-block")).not.toBeNull();
    expect(screen.getByText("const a = 1;")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy code" })).toBeInTheDocument();
  });

  it("renders an error item inline", () => {
    render(<TimelineItemView item={{ kind: "error", id: "e1", seq: 2, content: "boom" }} />);
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("renders a notice", () => {
    render(
      <TimelineItemView
        item={{ kind: "notice", id: "n1", seq: 2, content: "Stopped.", tone: "warning" }}
      />
    );
    expect(screen.getByText("Stopped.")).toBeInTheDocument();
  });
});
