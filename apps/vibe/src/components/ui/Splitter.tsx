// components/ui/Splitter.tsx — a draggable, keyboard-operable pane divider.
//
// Pointer capture means a fast drag that leaves the element keeps resizing,
// and the arrow keys mean the same adjustment is available without a mouse.
// Home/End jump to the limits; double-click restores the default.

import { useCallback, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

export interface SplitterProps {
  /** Current size of the pane being resized, in px. */
  value: number;
  min: number;
  max: number;
  onChange: (next: number) => void;
  /** Restored on double-click. */
  defaultValue?: number;
  /** "vertical" splits left/right (the divider is a vertical line). */
  orientation?: "vertical" | "horizontal";
  /** The controlled pane sits BEFORE the splitter, so dragging toward the
   *  start edge shrinks it. Default assumes the pane is after the splitter. */
  invert?: boolean;
  label: string;
  /** Keyboard step in px. Shift multiplies it by four. */
  step?: number;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export function Splitter({
  value,
  min,
  max,
  onChange,
  defaultValue,
  orientation = "vertical",
  invert = false,
  label,
  step = 16,
}: SplitterProps) {
  const [dragging, setDragging] = useState(false);
  const originRef = useRef<{ pointer: number; value: number } | null>(null);
  const axis = orientation === "horizontal" ? "y" : "x";

  const coordinate = (event: PointerEvent<HTMLDivElement>) =>
    axis === "y" ? event.clientY : event.clientX;

  const handlePointerDown = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      originRef.current = { pointer: coordinate(event), value };
      setDragging(true);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [value, axis]
  );

  const handlePointerMove = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      const origin = originRef.current;
      if (!origin) return;
      const delta = coordinate(event) - origin.pointer;
      onChange(clamp(origin.value + (invert ? -delta : delta), min, max));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [invert, max, min, onChange, axis]
  );

  const endDrag = useCallback((event: PointerEvent<HTMLDivElement>) => {
    originRef.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      const size = event.shiftKey ? step * 4 : step;
      const decrease = axis === "y" ? "ArrowUp" : "ArrowLeft";
      const increase = axis === "y" ? "ArrowDown" : "ArrowRight";
      let next: number | null = null;

      if (event.key === decrease) next = value + (invert ? size : -size);
      else if (event.key === increase) next = value + (invert ? -size : size);
      else if (event.key === "Home") next = min;
      else if (event.key === "End") next = max;

      if (next === null) return;
      event.preventDefault();
      onChange(clamp(next, min, max));
    },
    [axis, invert, max, min, onChange, step, value]
  );

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation={orientation}
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={Math.round(min)}
      aria-valuemax={Math.round(max)}
      className="splitter"
      data-dragging={dragging ? "true" : undefined}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={handleKeyDown}
      onDoubleClick={() => {
        if (typeof defaultValue === "number") onChange(clamp(defaultValue, min, max));
      }}
    />
  );
}
