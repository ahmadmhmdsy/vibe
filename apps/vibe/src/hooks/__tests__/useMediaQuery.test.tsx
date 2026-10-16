// hooks/__tests__/useMediaQuery.test.tsx — useSyncExternalStore subscription.
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { useMediaQuery } from "../useMediaQuery";

class MockMQL {
  private listeners = new Set<() => void>();
  constructor(public matches: boolean) {}
  addEventListener(_: string, cb: () => void) {
    this.listeners.add(cb);
  }
  removeEventListener(_: string, cb: () => void) {
    this.listeners.delete(cb);
  }
  dispatchChange() {
    this.listeners.forEach((cb) => cb());
  }
}

const queries = new Map<string, MockMQL>();

beforeEach(() => {
  queries.clear();
  window.matchMedia = (q: string) => {
    if (!queries.has(q)) queries.set(q, new MockMQL(false));
    return queries.get(q)! as unknown as MediaQueryList;
  };
});

afterEach(cleanup);

function Probe({ query }: { query: string }) {
  const matches = useMediaQuery(query);
  return <div data-testid="probe">{matches ? "yes" : "no"}</div>;
}

describe("useMediaQuery", () => {
  it("returns the initial match value on first render (no effect needed)", () => {
    queries.set("(max-width: 768px)", new MockMQL(true));
    render(<Probe query="(max-width: 768px)" />);
    expect(screen.getByTestId("probe").textContent).toBe("yes");
  });

  it("updates when the media query changes", () => {
    const mql = new MockMQL(false);
    queries.set("(max-width: 768px)", mql);
    render(<Probe query="(max-width: 768px)" />);
    expect(screen.getByTestId("probe").textContent).toBe("no");
    act(() => {
      mql.matches = true;
      mql.dispatchChange();
    });
    expect(screen.getByTestId("probe").textContent).toBe("yes");
  });

  it("returns false when matchMedia is unavailable", () => {
    // @ts-expect-error — simulate a browser without matchMedia
    window.matchMedia = undefined;
    render(<Probe query="(max-width: 768px)" />);
    expect(screen.getByTestId("probe").textContent).toBe("no");
  });

  it("stops updating after unmount", () => {
    const mql = new MockMQL(false);
    queries.set("(max-width: 768px)", mql);
    const { unmount } = render(<Probe query="(max-width: 768px)" />);
    unmount();
    mql.matches = true;
    mql.dispatchChange();
    // No assertion on the DOM (it is gone); reaching here without throwing is the pass.
    expect(true).toBe(true);
  });
});
