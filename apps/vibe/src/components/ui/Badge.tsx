// components/ui/Badge.tsx — a small, non-interactive status label.
import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "accent" | "success" | "danger" | "warning" | "info";

export interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = "neutral", children, className }: BadgeProps) {
  return (
    <span className={["badge", `badge-${tone}`, className].filter(Boolean).join(" ")}>
      {children}
    </span>
  );
}
