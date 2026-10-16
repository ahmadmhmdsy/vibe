// apps/vibe/src/features/preview/store.ts
import { create } from "zustand";
import { api } from "../../lib/api";

export interface PreviewState {
  url: string | null;
  isRunning: boolean;
  loading: boolean;
  error: string | null;
}

/** Stable empty value: a selector that returned a new object each render would
 * make zustand re-subscribe forever. */
export const EMPTY_PREVIEW: PreviewState = {
  url: null,
  isRunning: false,
  loading: false,
  error: null,
};

interface PreviewStore {
  /** Keyed by session: one global url/status bled across a session switch. */
  bySession: Record<string, PreviewState>;
  run: (sid: string) => Promise<void>;
  stop: (sid: string) => Promise<void>;
  poll: (sid: string) => Promise<void>;
}

const patch = (
  state: PreviewStore,
  sid: string,
  next: Partial<PreviewState>
): Partial<PreviewStore> => ({
  bySession: { ...state.bySession, [sid]: { ...(state.bySession[sid] ?? EMPTY_PREVIEW), ...next } },
});

export const usePreviewStore = create<PreviewStore>((set) => ({
  bySession: {},
  run: async (sid) => {
    set((s) => patch(s, sid, { loading: true, error: null }));
    try {
      const { url, is_running } = await api.runPreview(sid);
      set((s) => patch(s, sid, { url, isRunning: is_running, loading: false }));
    } catch (e) {
      set((s) =>
        patch(s, sid, {
          loading: false,
          error: e instanceof Error ? e.message : "Failed to start the dev server.",
        })
      );
    }
  },
  stop: async (sid) => {
    try {
      await api.stopPreview(sid);
      set((s) => patch(s, sid, { url: null, isRunning: false, error: null }));
    } catch (e) {
      set((s) =>
        patch(s, sid, {
          error: e instanceof Error ? e.message : "Failed to stop the dev server.",
        })
      );
    }
  },
  poll: async (sid) => {
    try {
      const { url, is_running } = await api.getPreview(sid);
      set((s) => patch(s, sid, { url, isRunning: is_running, error: null }));
    } catch {
      // Transient poll failure — keep the last known state.
    }
  },
}));
