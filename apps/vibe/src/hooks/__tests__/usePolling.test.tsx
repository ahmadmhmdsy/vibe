// hooks/__tests__/usePolling.test.tsx — polling must outlive a backend restart.
import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { usePolling } from "../usePolling";

describe("usePolling", () => {
  it("keeps polling at a slow cadence after repeated failures", async () => {
    const callback = vi.fn().mockRejectedValue(new Error("backend down"));
    renderHook(() =>
      usePolling(callback, { interval: 5, backoffBase: 5, recoveryInterval: 10, maxRetries: 2 })
    );

    // The old behaviour stopped for good once maxRetries was reached.
    await waitFor(() => expect(callback.mock.calls.length).toBeGreaterThan(4), { timeout: 2000 });
  });

  it("returns to the normal cadence once a call succeeds", async () => {
    const callback = vi
      .fn()
      .mockRejectedValueOnce(new Error("backend down"))
      .mockRejectedValueOnce(new Error("backend down"))
      .mockResolvedValue(undefined);
    renderHook(() =>
      usePolling(callback, { interval: 5, backoffBase: 5, recoveryInterval: 10, maxRetries: 2 })
    );

    await waitFor(() => expect(callback.mock.calls.length).toBeGreaterThanOrEqual(3), {
      timeout: 2000,
    });
  });

  it("does not poll while disabled", async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, { interval: 5, enabled: false }));
    await new Promise((r) => setTimeout(r, 50));
    expect(callback).not.toHaveBeenCalled();
  });
});
