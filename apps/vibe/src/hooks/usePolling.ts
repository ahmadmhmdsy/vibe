// hooks/usePolling.ts — Coordinated polling with automatic cleanup.
// Prevents memory leaks and ensures only one poll runs at a time.

import { useEffect, useRef, useCallback } from "react";

interface PollingOptions {
  /** Poll interval in milliseconds */
  interval: number;
  /** Whether polling is active */
  enabled?: boolean;
  /** Consecutive failures before falling back to recoveryInterval */
  maxRetries?: number;
  /** Base delay for exponential backoff (ms) */
  backoffBase?: number;
  /** Slow cadence used once maxRetries consecutive failures have happened.
   *  Polling must outlive a backend restart: stopping for good would leave
   *  usage, approvals, and the file list silently stale for the rest of the
   *  session. */
  recoveryInterval?: number;
}

export function usePolling(
  callback: () => Promise<void> | void,
  { interval, enabled = true, maxRetries = 3, backoffBase = 1000, recoveryInterval = 15000 }: PollingOptions
) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  const retriesRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      clear();
      return;
    }

    let cancelled = false;

    const tick = async () => {
      if (cancelled) return;

      try {
        await callbackRef.current();
        retriesRef.current = 0;
      } catch {
        retriesRef.current++;
      }

      if (!cancelled) {
        const delay =
          retriesRef.current >= maxRetries
            ? recoveryInterval
            : retriesRef.current > 0
              ? backoffBase * Math.pow(2, retriesRef.current - 1)
              : interval;
        timerRef.current = setTimeout(tick, delay);
      }
    };

    tick();

    return () => {
      cancelled = true;
      clear();
    };
  }, [interval, enabled, maxRetries, backoffBase, recoveryInterval, clear]);

  return { clear };
}
