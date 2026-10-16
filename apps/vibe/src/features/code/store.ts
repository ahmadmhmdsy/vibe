// apps/vibe/src/features/code/store.ts
import { create } from "zustand";
import { api } from "../../lib/api";

interface CodeState {
  files: string[];
  selectedFile: string | null;
  contents: Record<string, string>;
  setFiles: (files: string[]) => void;
  setSelectedFile: (file: string | null) => void;
  setContent: (path: string, content: string) => void;
  loadFiles: (sid: string) => Promise<void>;
  loadFile: (sid: string, path: string) => Promise<void>;
  saveFile: (sid: string, path: string, content: string) => Promise<void>;
}

export const useCodeStore = create<CodeState>((set) => ({
  files: [],
  selectedFile: null,
  contents: {},
  setFiles: (files) => set({ files }),
  setSelectedFile: (selectedFile) => set({ selectedFile }),
  setContent: (path, content) => set((s) => ({ contents: { ...s.contents, [path]: content } })),
  // Both reads propagate their failure. They used to resolve to an empty
  // string or an empty list, so a backend outage was indistinguishable from
  // "this session has no files" and CodePanel's error handling never ran.
  loadFiles: async (sid) => {
    const files = await api.listFiles(sid);
    set({ files });
  },
  loadFile: async (sid, path) => {
    const { content } = await api.readFile(sid, path);
    set((s) => ({ contents: { ...s.contents, [path]: content } }));
  },
  saveFile: async (sid, path, content) => {
    set((s) => ({ contents: { ...s.contents, [path]: content } }));
    await api.writeFile(sid, path, content);
  },
}));
