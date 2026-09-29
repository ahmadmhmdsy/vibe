// apps/vibe/src/features/sessions/store.ts
import { create } from "zustand";
import { api, type Session } from "../../lib/api";
import { useChatStore } from "../chat/store";

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
    // Use the model currently selected in the picker (chat store), so new
    // sessions inherit the user's choice instead of a hardcoded default.
    const model = useChatStore.getState().model;
    const { id } = await api.createSession(model);
    await get().load();
    set({ activeId: id });
    return id;
  },
  remove: async (id) => {
    await api.deleteSession(id);
    const { sessions } = get();
    // Fix a stale activeId: if the deleted session was active, select the
    // next remaining session (or null) so the UI never points at a ghost.
    if (get().activeId === id) {
      set({ activeId: sessions.find((s) => s.id !== id)?.id ?? null });
    }
    await get().load();
  },
  select: (id) => set({ activeId: id }),
}));
