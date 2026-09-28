// apps/vibe/src/features/code/store.ts
import { create } from "zustand";

interface CodeState {
  files: string[];
  selectedFile: string | null;
  setFiles: (files: string[]) => void;
  setSelectedFile: (file: string | null) => void;
}

export const useCodeStore = create<CodeState>((set) => ({
  files: [],
  selectedFile: null,
  setFiles: (files) => set({ files }),
  setSelectedFile: (selectedFile) => set({ selectedFile }),
}));
