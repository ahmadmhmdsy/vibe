// apps/vibe/src/features/sessions/store.ts
import { create } from "zustand";
import { api, type Session } from "../../lib/api";

interface SessionsState {
  sessions: Session[];
  activeId: string | null;
  load: () => Promise<void>;
  create: () => Promise<string>;
  remove: (id: string) => Promise<void>;
  select: (id: string) => void;
}

export const useSessionsStore = create<SessionsState>((set, get) => ({
  sessions: [],
  activeId: null,
  load: async () => {
    const sessions = await api.listSessions();
    set({ sessions, activeId: get().activeId ?? sessions[0]?.id ?? null });
  },
  create: async () => {
    const { id } = await api.createSession({ provider_id: "openai", model_id: "gpt-4o" });
    await get().load();
    set({ activeId: id });
    return id;
  },
  remove: async (id) => {
    await api.deleteSession(id);
    await get().load();
  },
  select: (id) => set({ activeId: id }),
}));
