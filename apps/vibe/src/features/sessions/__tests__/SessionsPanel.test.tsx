// apps/vibe/src/features/sessions/__tests__/SessionsPanel.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionsPanel } from "../SessionsPanel";

describe("SessionsPanel", () => {
  it("renders a new session button", () => {
    render(<SessionsPanel />);
    expect(screen.getByRole("button", { name: /new/i })).toBeInTheDocument();
  });
});
