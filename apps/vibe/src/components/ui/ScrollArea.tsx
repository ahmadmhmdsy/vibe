// components/ui/ScrollArea.tsx — a region that scrolls without growing the shell.
import type { ReactNode } from "react";

export interface ScrollAreaProps {
  children: ReactNode;
  className?: string;
  /** Accessible name, for a scrollable region that is a landmark in its own
   *  right. Omit for a region whose content is already labelled by a heading. */
  label?: string;
  style?: React.CSSProperties;
}

export function ScrollArea({ children, className, label, style }: ScrollAreaProps) {
  return (
    <div
      className={["scroll-region", className].filter(Boolean).join(" ")}
      style={style}
      tabIndex={0}
      role={label ? "region" : undefined}
      aria-label={label}
    >
      {children}
    </div>
  );
}
