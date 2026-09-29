// apps/vibe/src/features/chat/ApprovalCard.tsx
import { useEffect, useState } from "react";
import type { Approval } from "../../lib/api";
import { Button } from "../../components/ui/Button";

const POLICY_KEY = "vibe.approvalPolicy";

function loadPolicy(): string[] {
  try {
    const raw = localStorage.getItem(POLICY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function savePolicy(patterns: string[]) {
  localStorage.setItem(POLICY_KEY, JSON.stringify(patterns));
}

interface ApprovalCardProps {
  approval: Approval;
  onApprove: () => void;
  onDeny: () => void;
}

export function ApprovalCard({ approval, onApprove, onDeny }: ApprovalCardProps) {
  const [alwaysAllow, setAlwaysAllow] = useState(false);
  const [status, setStatus] = useState<"pending" | "approved" | "denied">("pending");

  // Auto-approve when the saved policy covers every requested package.
  useEffect(() => {
    const policy = loadPolicy();
    if (approval.packages.length > 0 && approval.packages.every((p) => policy.includes(p))) {
      onApprove();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approval.id]);

  const approve = () => {
    if (alwaysAllow) {
      savePolicy([...new Set([...loadPolicy(), ...approval.packages])]);
    }
    setStatus("approved");
    onApprove();
  };

  const deny = () => {
    setStatus("denied");
    onDeny();
  };

  return (
    <div className="approval-card" data-status={status}>
      <div className="approval-title">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M8 1.5L15 14H1L8 1.5z" strokeLinejoin="round" />
          <path d="M8 6.5v3" strokeLinecap="round" />
          <circle cx="8" cy="11.2" r="0.4" fill="currentColor" />
        </svg>
        Approval needed
      </div>
      <div className="approval-packages">
        {approval.packages.map((p) => (
          <span key={p} className="approval-package">{p}</span>
        ))}
      </div>
      <div className="approval-hint">The agent wants to install these packages.</div>
      {status === "pending" ? (
        <>
          <div className="approval-actions">
            <Button variant="primary" size="sm" onClick={approve}>
              Approve
            </Button>
            <Button variant="secondary" size="sm" onClick={deny}>
              Deny
            </Button>
            <label className="approval-always">
              <input
                type="checkbox"
                checked={alwaysAllow}
                onChange={(e) => setAlwaysAllow(e.target.checked)}
              />
              Always allow
            </label>
          </div>
        </>
      ) : (
        <div className={`approval-status ${status === "approved" ? "approval-status-approved" : "approval-status-denied"}`}>
          {status === "approved" ? "Approved" : "Denied"}
        </div>
      )}
    </div>
  );
}
