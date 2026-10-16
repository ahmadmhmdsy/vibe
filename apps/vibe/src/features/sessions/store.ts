// features/sessions/store.ts — Session management store.
// Manages session list, active session, and CRUD operations.

import { create } from "zustand";
import { api, type ProjectSource, type Session } from "../../lib/api";

interface SessionsState {
  sessions: Session[];
  activeId: string | null;
  load: () => Promise<void>;
  create: (
    model?: { provider_id: string; model_id: string },
    source?: ProjectSource
  ) => Promise<string>;
  remove: (id: string) => Promise<void>;
  select: (id: string) => void;
}

// Default model — used when no model is provided
const DEFAULT_MODEL = { provider_id: "opencode-go", model_id: "kimi-k3" };

export const useSessionsStore = create<SessionsState>((set, get) => ({
  sessions: [],
  activeId: null,
  load: async () => {
    const sessions = await api.listSessions();
    set({ sessions, activeId: get().activeId ?? sessions[0]?.id ?? null });
  },
  create: async (model = DEFAULT_MODEL, source) => {
    const { id } = await api.createSession(model, source);
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
