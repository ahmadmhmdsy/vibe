// apps/vibe/src/components/ui/EmptyState.tsx
import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, body, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon" aria-hidden="true">{icon}</div>}
      <h2>{title}</h2>
      {body && <p className="muted">{body}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
