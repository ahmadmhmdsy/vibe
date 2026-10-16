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
  try {
    localStorage.setItem(POLICY_KEY, JSON.stringify(patterns));
  } catch {
    // Storage unavailable (private mode, quota). The approval still applies to
    // this request; only remembering it for next time is lost.
  }
}

interface ApprovalCardProps {
  approval: Approval;
  /** May reject; the card stays actionable and reports the failure. */
  onApprove: () => void | Promise<void>;
  onDeny: () => void | Promise<void>;
}

export function ApprovalCard({ approval, onApprove, onDeny }: ApprovalCardProps) {
  const [alwaysAllow, setAlwaysAllow] = useState(false);
  const [status, setStatus] = useState<"pending" | "approved" | "denied">("pending");
  const [error, setError] = useState<string | null>(null);

  // Auto-approve when the saved policy covers every requested package.
  useEffect(() => {
    const policy = loadPolicy();
    if (approval.packages.length > 0 && approval.packages.every((p) => policy.includes(p))) {
      onApprove();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approval.id]);

  /** Apply a decision, but only claim success once it is actually recorded.
   *
   * Handlers that return nothing stay synchronous; promise-returning ones are
   * awaited and their rejection becomes a visible error instead of a success
   * the server never saw.
   */
  const settle = (result: void | Promise<void>, onSuccess: () => void, failure: string) => {
    if (result && typeof (result as Promise<void>).then === "function") {
      (result as Promise<void>).then(onSuccess, () => setError(failure));
    } else {
      onSuccess();
    }
  };

  const approve = () => {
    setError(null);
    if (alwaysAllow) {
      savePolicy([...new Set([...loadPolicy(), ...approval.packages])]);
    }
    settle(
      onApprove(),
      () => setStatus("approved"),
      "Could not send the approval. Check the connection and try again."
    );
  };

  const deny = () => {
    setError(null);
    settle(
      onDeny(),
      () => setStatus("denied"),
      "Could not send the denial. Check the connection and try again."
    );
  };

  const count = approval.packages.length;

  return (
    <div
      className="approval-card"
      data-status={status}
      role="group"
      aria-label={`Approval needed for ${count} package${count === 1 ? "" : "s"}`}
    >
      <div className="approval-title">
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path d="M8 1.5L15 14H1L8 1.5z" strokeLinejoin="round" />
          <path d="M8 6.5v3" strokeLinecap="round" />
          <circle cx="8" cy="11.2" r="0.4" fill="currentColor" />
        </svg>
        Approval needed
      </div>

      <p className="approval-hint">
        The agent wants to install {count === 1 ? "this package" : "these packages"} into this
        session's workspace.
      </p>

      <div className="approval-packages">
        {approval.packages.map((p) => (
          <span key={p} className="approval-package">
            {p}
          </span>
        ))}
      </div>

      {error && (
        <p className="approval-error" role="alert">
          {error}
        </p>
      )}

      {status === "pending" ? (
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
      ) : (
        <div
          className={`approval-status ${status === "approved" ? "approval-status-approved" : "approval-status-denied"}`}
        >
          {status === "approved" ? (
            <>
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="M3 8.5l3.5 3.5L13 4.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Approved
            </>
          ) : (
            <>
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
              </svg>
              Denied
            </>
          )}
        </div>
      )}
    </div>
  );
}
