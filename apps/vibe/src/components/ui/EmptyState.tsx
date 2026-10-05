// components/ui/EmptyState.tsx — Empty state placeholder.

import { memo, type ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  body?: string;
  action?: ReactNode;
  /** Heading level (default: h2) */
  headingLevel?: "h1" | "h2" | "h3" | "h4";
}

export const EmptyState = memo(function EmptyState({
  icon,
  title,
  body,
  action,
  headingLevel: Heading = "h2",
}: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon && (
        <div className="empty-state-icon" aria-hidden="true">
          {icon}
        </div>
      )}
      <Heading>{title}</Heading>
      {body && <p className="muted">{body}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
});
