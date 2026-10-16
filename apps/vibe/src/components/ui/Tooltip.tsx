// components/ui/Tooltip.tsx — a visual affordance, never an accessible name.
//
// Two rules make this component correct rather than merely present:
//
// 1. The tooltip is aria-hidden and has no role. The control it wraps must
//    carry its own accessible name (IconButton requires `label` and sets
//    aria-label). The previous version rendered a role="tooltip" node for
//    every control on the page — 79 of them, none aria-hidden, none linked
//    through aria-describedby — which is a large amount of noise in the
//    accessibility tree for zero benefit.
// 2. The tooltip is portalled to document.body and positioned with fixed
//    coordinates measured from the trigger. An absolutely positioned tooltip
//    inside the app shell gets clipped: the shell, the panels, and every
//    scroll region set overflow, and a tooltip in the header would render
//    above the top of the window.

import { createPortal } from "react-dom";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";

export type TooltipSide = "top" | "bottom" | "left" | "right";

export interface TooltipProps {
  /** Visible text. Also the wording a screen reader already gets from the
   *  wrapped control, so keep the two in sync. */
  label: string;
  children: ReactNode;
  /** Which side of the trigger to prefer. The tooltip is clamped into the
   *  viewport, so this is a preference and not a guarantee. */
  side?: TooltipSide;
  /** Hover delay in ms. Keyboard focus shows immediately. */
  delay?: number;
  /** Suppress the tooltip, e.g. while a menu is open. */
  disabled?: boolean;
}

const SHOW_DELAY_MS = 400;
const EDGE_GAP = 8;

interface Position {
  top: number;
  left: number;
}

export function Tooltip({
  label,
  children,
  side = "top",
  delay = SHOW_DELAY_MS,
  disabled = false,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<Position | null>(null);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const hide = useCallback(() => {
    clearTimer();
    setVisible(false);
    setPosition(null);
  }, [clearTimer]);

  const show = useCallback(
    (immediate: boolean) => {
      if (disabled) return;
      clearTimer();
      if (immediate) {
        setVisible(true);
        return;
      }
      timerRef.current = window.setTimeout(() => setVisible(true), delay);
    },
    [clearTimer, delay, disabled]
  );

  useEffect(() => clearTimer, [clearTimer]);

  // Derived, not synced: flipping `disabled` while a tooltip is showing hides
  // it without an effect that calls setState during render.
  const active = visible && !disabled;

  // Measure after the tooltip is in the DOM but before the browser paints, so
  // the unpositioned state is never visible.
  useLayoutEffect(() => {
    if (!active) return;
    const wrap = wrapRef.current;
    const tip = tipRef.current;
    if (!wrap || !tip) return;

    const trigger = wrap.getBoundingClientRect();
    const box = tip.getBoundingClientRect();
    let top: number;
    let left: number;

    switch (side) {
      case "bottom":
        top = trigger.bottom + EDGE_GAP;
        left = trigger.left + trigger.width / 2 - box.width / 2;
        break;
      case "left":
        top = trigger.top + trigger.height / 2 - box.height / 2;
        left = trigger.left - EDGE_GAP - box.width;
        break;
      case "right":
        top = trigger.top + trigger.height / 2 - box.height / 2;
        left = trigger.right + EDGE_GAP;
        break;
      default:
        top = trigger.top - EDGE_GAP - box.height;
        left = trigger.left + trigger.width / 2 - box.width / 2;
    }

    top = Math.max(EDGE_GAP, Math.min(top, window.innerHeight - box.height - EDGE_GAP));
    left = Math.max(EDGE_GAP, Math.min(left, window.innerWidth - box.width - EDGE_GAP));
    setPosition({ top, left });
  }, [active, side]);

  // A fixed-position tooltip would drift away from its trigger on scroll or
  // resize; hiding it is simpler and more honest than chasing the rect.
  useEffect(() => {
    if (!active) return;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [active, hide]);

  return (
    <span
      ref={wrapRef}
      className="tooltip-wrap"
      onPointerEnter={() => show(false)}
      onPointerLeave={hide}
      onPointerDown={hide}
      onFocus={() => show(true)}
      onBlur={hide}
      onKeyDown={(event) => {
        if (event.key === "Escape") hide();
      }}
    >
      {children}
      {active && typeof document !== "undefined"
        ? createPortal(
            <span
              ref={tipRef}
              className="tooltip"
              data-side={side}
              aria-hidden="true"
              style={{
                top: position ? `${position.top}px` : 0,
                left: position ? `${position.left}px` : 0,
                visibility: position ? "visible" : "hidden",
              }}
            >
              {label}
            </span>,
            document.body
          )
        : null}
    </span>
  );
}
