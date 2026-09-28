// apps/vibe/src/features/chat/store.ts
import { create } from "zustand";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tool_calls?: { id: string; name: string; arguments: Record<string, unknown> }[];
}

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  model: { provider_id: string; model_id: string };
  setModel: (m: { provider_id: string; model_id: string }) => void;
  addMessage: (m: ChatMessage) => void;
  appendChunk: (text: string) => void;
  setStreaming: (v: boolean) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  model: { provider_id: "openai", model_id: "gpt-4o" },
  setModel: (model) => set({ model }),
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  appendChunk: (text) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + text };
      } else {
        msgs.push({ role: "assistant", content: text });
      }
      return { messages: msgs };
    }),
  setStreaming: (isStreaming) => set({ isStreaming }),
}));
