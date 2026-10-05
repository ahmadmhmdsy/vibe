// components/ui/IconButton.tsx — Icon-only button with tooltip.

import { forwardRef, memo, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Tooltip } from "./Tooltip";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible name — required (icon-only control). */
  label: string;
  children: ReactNode;
}

export const IconButton = memo(
  forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
    { label, children, className, ...rest },
    ref
  ) {
    return (
      <Tooltip label={label}>
        <button
          ref={ref}
          className={["icon-btn", className].filter(Boolean).join(" ")}
          aria-label={label}
          {...rest}
        >
          {children}
        </button>
      </Tooltip>
    );
  })
);
