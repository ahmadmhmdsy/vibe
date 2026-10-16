// apps/vibe/src/hooks/__tests__/usePollingVisibility.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { usePolling } from "../usePolling";

const setHidden = (hidden: boolean) =>
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });

afterEach(() => {
  Reflect.deleteProperty(document, "hidden");
  vi.restoreAllMocks();
});

describe("usePolling tab visibility", () => {
  it("does not call the backend while the document is hidden", async () => {
    setHidden(true);
    const cb = vi.fn().mockResolvedValue(undefined);
    const { unmount } = renderHook(() => usePolling(cb, { interval: 50 }));
    await new Promise((r) => setTimeout(r, 120));
    expect(cb).not.toHaveBeenCalled();
    unmount();
  });

  it("refreshes immediately when the document becomes visible again", async () => {
    setHidden(true);
    const cb = vi.fn().mockResolvedValue(undefined);
    const { unmount } = renderHook(() => usePolling(cb, { interval: 10_000 }));
    expect(cb).not.toHaveBeenCalled();

    setHidden(false);
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await waitFor(() => expect(cb).toHaveBeenCalledTimes(1));
    unmount();
  });
});
