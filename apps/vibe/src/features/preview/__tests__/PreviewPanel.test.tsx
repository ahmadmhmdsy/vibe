// apps/vibe/src/features/preview/__tests__/PreviewPanel.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { PreviewPanel } from "../PreviewPanel";

describe("PreviewPanel", () => {
  it("renders run/stop buttons", () => {
    render(<PreviewPanel sessionId="s1" />);
    expect(screen.getByRole("button", { name: /run/i })).toBeInTheDocument();
  });
});
