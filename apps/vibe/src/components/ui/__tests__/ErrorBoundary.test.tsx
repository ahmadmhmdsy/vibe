// apps/vibe/src/components/ui/__tests__/ErrorBoundary.test.tsx
// Covers the root boundary wired into main.tsx: a crash inside it must not
// blank the page, and everything outside it must keep rendering.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "../ErrorBoundary";

/** Throws on every render. */
function Exploding(): never {
  throw new Error("panel exploded");
}

/** Throws only while armed, so a recovery path can be observed. */
let armed = true;
function SometimesExploding() {
  if (armed) throw new Error("once");
  return <span>recovered child</span>;
}

afterEach(() => {
  cleanup();
  armed = true;
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("shows a fallback while its sibling outside the boundary still renders", () => {
    // React logs boundary catches; keep the suite output clean.
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <div>
        <span>outside sibling</span>
        <ErrorBoundary>
          <Exploding />
        </ErrorBoundary>
      </div>
    );

    expect(screen.getByText("outside sibling")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/panel exploded/);
    expect(screen.getByRole("button", { name: /dismiss/i })).toBeInTheDocument();
  });

  it("renders a custom fallback when one is supplied", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary fallback={<span>custom fallback</span>}>
        <Exploding />
      </ErrorBoundary>
    );
    expect(screen.getByText("custom fallback")).toBeInTheDocument();
  });

  it("recovers when the failing child stops failing", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <SometimesExploding />
      </ErrorBoundary>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();

    armed = false;
    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(screen.getByText("recovered child")).toBeInTheDocument();
  });
});
