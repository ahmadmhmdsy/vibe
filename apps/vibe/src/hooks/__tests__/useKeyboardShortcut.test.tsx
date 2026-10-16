// hooks/__tests__/useKeyboardShortcut.test.tsx — latest-ref pattern via effect.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { useKeyboardShortcut } from "../useKeyboardShortcut";

afterEach(cleanup);

interface ProbeProps {
  handler: () => void;
  meta?: boolean;
  key?: string;
  allowInInput?: boolean;
}

function Probe({ handler, meta = false, key = "k", allowInInput = false }: ProbeProps) {
  useKeyboardShortcut(handler, { meta, key, allowInInput });
  return null;
}

describe("useKeyboardShortcut", () => {
  it("calls the handler on the matching key", () => {
    const handler = vi.fn();
    render(<Probe handler={handler} />);
    fireEvent.keyDown(document, { key: "k" });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("does not call the handler on a non-matching key", () => {
    const handler = vi.fn();
    render(<Probe handler={handler} />);
    fireEvent.keyDown(document, { key: "j" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("requires meta when meta is true", () => {
    const handler = vi.fn();
    render(<Probe handler={handler} meta />);
    fireEvent.keyDown(document, { key: "k" });
    expect(handler).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("ignores meta when meta is false", () => {
    const handler = vi.fn();
    render(<Probe handler={handler} />);
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not fire in an input unless allowInInput", () => {
    const handler = vi.fn();
    render(
      <div>
        <input data-testid="input" />
        <Probe handler={handler} />
      </div>
    );
    fireEvent.keyDown(screen.getByTestId("input"), { key: "k" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("fires in an input when allowInInput is true", () => {
    const handler = vi.fn();
    render(
      <div>
        <input data-testid="input" />
        <Probe handler={handler} allowInInput />
      </div>
    );
    fireEvent.keyDown(screen.getByTestId("input"), { key: "k" });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("uses the latest handler after a re-render (ref updated in an effect)", () => {
    const handlerA = vi.fn();
    const handlerB = vi.fn();
    const { rerender } = render(<Probe handler={handlerA} />);
    rerender(<Probe handler={handlerB} />);
    fireEvent.keyDown(document, { key: "k" });
    expect(handlerA).not.toHaveBeenCalled();
    expect(handlerB).toHaveBeenCalledOnce();
  });
});
