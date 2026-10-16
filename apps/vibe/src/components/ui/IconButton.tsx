// components/ui/IconButton.tsx — icon-only button with a tooltip.

import { forwardRef, memo, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Tooltip, type TooltipSide } from "./Tooltip";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible name — required, because the visible content is an icon. */
  label: string;
  children: ReactNode;
  /** Which side the tooltip prefers. Header controls pass "bottom" so the
   *  tooltip does not render above the top of the window. */
  tooltipSide?: TooltipSide;
  /** Suppress the tooltip while a menu or dialog owns the interaction. */
  tooltipDisabled?: boolean;
}

export const IconButton = memo(
  forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
    { label, children, className, tooltipSide, tooltipDisabled, ...rest },
    ref
  ) {
    return (
      <Tooltip label={label} side={tooltipSide} disabled={tooltipDisabled}>
        <button
          ref={ref}
          type="button"
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
