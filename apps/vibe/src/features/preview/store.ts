// apps/vibe/src/features/preview/store.ts
import { create } from "zustand";

interface PreviewState {
  url: string | null;
  isRunning: boolean;
  consoleLogs: string;
  run: () => Promise<void>;
  stop: () => void;
}

export const usePreviewStore = create<PreviewState>((set) => ({
  url: null,
  isRunning: false,
  consoleLogs: "",
  run: async () => {
    set({ isRunning: true });
    // dev server URL comes from the backend; for MVP poll a known port
    set({ url: "http://127.0.0.1:5173/" });
  },
  stop: () => set({ isRunning: false, url: null }),
}));
