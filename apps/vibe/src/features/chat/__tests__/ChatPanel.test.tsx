// apps/vibe/src/features/chat/__tests__/ChatPanel.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatPanel } from "../ChatPanel";

describe("ChatPanel", () => {
  it("renders the composer", () => {
    render(<ChatPanel sessionId="s1" />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });
});
