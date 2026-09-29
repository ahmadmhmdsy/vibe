// apps/vibe/src/features/preview/store.ts
import { create } from "zustand";

interface PreviewState {
  url: string | null;
  isRunning: boolean;
  loading: boolean;
  error: string | null;
  run: () => Promise<void>;
  stop: () => void;
}

export const usePreviewStore = create<PreviewState>((set) => ({
  url: null,
  isRunning: false,
  loading: false,
  error: null,
  run: async () => {
    set({ isRunning: true, loading: true, error: null });
    // dev server URL comes from the backend; for MVP poll a known port
    set({ url: "http://127.0.0.1:5173/" });
    set({ loading: false });
  },
  stop: () => set({ isRunning: false, url: null, error: null }),
}));
