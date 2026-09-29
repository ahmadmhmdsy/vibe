// apps/vibe/src/features/chat/store.ts
import { create } from "zustand";
import { api, type Message } from "../../lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tool_calls?: { id: string; name: string; arguments: Record<string, unknown> }[];
}

interface ChatState {
  messagesBySession: Record<string, ChatMessage[]>;
  isStreamingBySession: Record<string, boolean>;
  stopRequested: Record<string, boolean>;
  model: { provider_id: string; model_id: string };
  setModel: (m: { provider_id: string; model_id: string }) => void;
  addMessage: (sid: string, m: ChatMessage) => void;
  appendChunk: (sid: string, text: string) => void;
  setStreaming: (sid: string, v: boolean) => void;
  requestStop: (sid: string) => void;
  loadHistory: (sid: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messagesBySession: {},
  isStreamingBySession: {},
  stopRequested: {},
  model: { provider_id: "openai", model_id: "gpt-4o" },
  setModel: (model) => set({ model }),
  addMessage: (sid, m) =>
    set((s) => ({
      messagesBySession: { ...s.messagesBySession, [sid]: [...(s.messagesBySession[sid] ?? []), m] },
    })),
  appendChunk: (sid, text) =>
    set((s) => {
      const msgs = [...(s.messagesBySession[sid] ?? [])];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + text };
      } else {
        msgs.push({ role: "assistant", content: text });
      }
      return { messagesBySession: { ...s.messagesBySession, [sid]: msgs } };
    }),
  setStreaming: (sid, v) =>
    set((s) => ({ isStreamingBySession: { ...s.isStreamingBySession, [sid]: v } })),
  requestStop: (sid) =>
    set((s) => ({ stopRequested: { ...s.stopRequested, [sid]: true } })),
  loadHistory: async (sid) => {
    const history = await api.getMessages(sid);
    set((s) => {
      // Don't clobber messages the user already sent this session.
      if ((s.messagesBySession[sid] ?? []).length > 0) return {};
      return {
        messagesBySession: {
          ...s.messagesBySession,
          [sid]: history.map((m: Message) => ({ role: m.role, content: m.content })),
        },
      };
    });
  },
}));
