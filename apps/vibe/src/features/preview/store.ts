// apps/vibe/src/features/preview/store.ts
import { create } from "zustand";
import { api } from "../../lib/api";

interface PreviewState {
  url: string | null;
  isRunning: boolean;
  loading: boolean;
  error: string | null;
  run: (sid: string) => Promise<void>;
  stop: (sid: string) => Promise<void>;
  poll: (sid: string) => Promise<void>;
}

export const usePreviewStore = create<PreviewState>((set) => ({
  url: null,
  isRunning: false,
  loading: false,
  error: null,
  run: async (sid) => {
    set({ loading: true, error: null });
    try {
      const { url, is_running } = await api.runPreview(sid);
      set({ url, isRunning: is_running, loading: false });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : "Failed to start the dev server." });
    }
  },
  stop: async (sid) => {
    try {
      await api.stopPreview(sid);
      set({ url: null, isRunning: false, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : "Failed to stop the dev server." });
    }
  },
  poll: async (sid) => {
    try {
      const { url, is_running } = await api.getPreview(sid);
      set({ url, isRunning: is_running, error: null });
    } catch {
      // Transient poll failure — keep the last known state.
    }
  },
}));
