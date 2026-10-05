// apps/vibe/src/features/chat/__tests__/ApprovalCard.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    approve: vi.fn().mockResolvedValue({ ok: true }),
    deny: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

import { type Approval } from "../../../lib/api";
import { ApprovalCard } from "../ApprovalCard";

const approval: Approval = {
  id: "a1",
  session_id: "s1",
  packages: ["react", "zustand"],
  status: "pending",
  created_at: "2026-09-29",
};

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.clearAllMocks();
});

describe("ApprovalCard", () => {
  it("renders the package list", () => {
    render(<ApprovalCard approval={approval} onApprove={() => {}} onDeny={() => {}} />);
    expect(screen.getByText("react")).toBeInTheDocument();
    expect(screen.getByText("zustand")).toBeInTheDocument();
  });

  it("calls onApprove when Approve is clicked", () => {
    const onApprove = vi.fn();
    render(<ApprovalCard approval={approval} onApprove={onApprove} onDeny={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    expect(onApprove).toHaveBeenCalled();
  });

  it("calls onDeny when Deny is clicked", () => {
    const onDeny = vi.fn();
    render(<ApprovalCard approval={approval} onApprove={() => {}} onDeny={onDeny} />);
    fireEvent.click(screen.getByRole("button", { name: /^deny$/i }));
    expect(onDeny).toHaveBeenCalled();
  });

  it("always-allow persists the packages to localStorage", () => {
    render(<ApprovalCard approval={approval} onApprove={() => {}} onDeny={() => {}} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /always allow/i }));
    fireEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    const policy = JSON.parse(localStorage.getItem("vibe.approvalPolicy") ?? "[]");
    expect(policy).toContain("react");
    expect(policy).toContain("zustand");
  });

  it("auto-approves when the policy covers the packages", () => {
    localStorage.setItem("vibe.approvalPolicy", JSON.stringify(["react", "zustand"]));
    const onApprove = vi.fn();
    render(<ApprovalCard approval={approval} onApprove={onApprove} onDeny={() => {}} />);
    expect(onApprove).toHaveBeenCalled();
  });

  it("does not auto-approve when the policy covers only some packages", () => {
    localStorage.setItem("vibe.approvalPolicy", JSON.stringify(["react"]));
    const onApprove = vi.fn();
    render(<ApprovalCard approval={approval} onApprove={onApprove} onDeny={() => {}} />);
    expect(onApprove).not.toHaveBeenCalled();
  });
});
