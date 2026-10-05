// apps/vibe/src/features/chat/store.ts
import { create } from "zustand";
import { api, type Message } from "../../lib/api";

export interface ChatMessage {
  /** Stable identity: index keys made React reuse the wrong node after an insert. */
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_calls?: { id: string; name: string; arguments: Record<string, unknown> }[];
}

/** Monotonic within a page load; ids only need to be unique inside one list.
 * The "msg-" prefix keeps them from colliding with ids built elsewhere. */
let idCounter = 0;
export function nextMessageId(): string {
  idCounter += 1;
  return `msg-${idCounter}`;
}

/** Messages fetched per page. Matches the backend default, so opening a
 * session is one request rather than a page plus a follow-up. */
const PAGE_SIZE = 200;

const toChatMessage = (m: Message): ChatMessage => ({
  id: nextMessageId(),
  role: m.role,
  content: m.content,
});

interface ChatState {
  messagesBySession: Record<string, ChatMessage[]>;
  isStreamingBySession: Record<string, boolean>;
  /** The assistant message currently accepting streamed text, per session. */
  streamingMessageIdBySession: Record<string, string | null>;
  stopRequested: Record<string, boolean>;
  /** How many messages the server holds per session, so the UI can tell
   * whether loading older ones would return anything. */
  historyTotalBySession: Record<string, number>;
  model: { provider_id: string; model_id: string };
  setModel: (m: { provider_id: string; model_id: string }) => void;
  addMessage: (sid: string, m: Omit<ChatMessage, "id">) => void;
  beginStream: (sid: string) => void;
  appendChunk: (sid: string, text: string) => void;
  endStream: (sid: string) => void;
  requestStop: (sid: string) => void;
  loadHistory: (sid: string) => Promise<void>;
  /** Fetch the page of messages immediately before the oldest one held. */
  loadMoreHistory: (sid: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messagesBySession: {},
  isStreamingBySession: {},
  streamingMessageIdBySession: {},
  stopRequested: {},
  historyTotalBySession: {},
  model: { provider_id: "opencode-go", model_id: "kimi-k3" },
  setModel: (model) => set({ model }),
  addMessage: (sid, m) =>
    set((s) => ({
      messagesBySession: {
        ...s.messagesBySession,
        [sid]: [...(s.messagesBySession[sid] ?? []), { ...m, id: nextMessageId() }],
      },
    })),
  beginStream: (sid) =>
    set((s) => ({
      // Point the stream at a fresh message: text for this turn must never land
      // in the previous turn's bubble, and the stop latch is per-turn.
      streamingMessageIdBySession: { ...s.streamingMessageIdBySession, [sid]: null },
      isStreamingBySession: { ...s.isStreamingBySession, [sid]: true },
      stopRequested: { ...s.stopRequested, [sid]: false },
    })),
  appendChunk: (sid, text) =>
    set((s) => {
      const msgs = [...(s.messagesBySession[sid] ?? [])];
      const targetId = s.streamingMessageIdBySession[sid] ?? null;
      const index = targetId ? msgs.findIndex((m) => m.id === targetId) : -1;
      if (index >= 0) {
        // Append only to the message this turn is streaming into; a finished
        // message is never mutated by a late or replayed chunk.
        msgs[index] = { ...msgs[index], content: msgs[index].content + text };
        return { messagesBySession: { ...s.messagesBySession, [sid]: msgs } };
      }
      const id = nextMessageId();
      msgs.push({ id, role: "assistant", content: text });
      return {
        messagesBySession: { ...s.messagesBySession, [sid]: msgs },
        streamingMessageIdBySession: { ...s.streamingMessageIdBySession, [sid]: id },
      };
    }),
  endStream: (sid) =>
    set((s) => ({
      isStreamingBySession: { ...s.isStreamingBySession, [sid]: false },
      streamingMessageIdBySession: { ...s.streamingMessageIdBySession, [sid]: null },
    })),
  requestStop: (sid) => set((s) => ({ stopRequested: { ...s.stopRequested, [sid]: true } })),
  loadHistory: async (sid) => {
    const { messages: history, total } = await api.getMessages(sid, { limit: PAGE_SIZE });
    set((s) => {
      // Don't clobber messages the user already sent this session.
      if ((s.messagesBySession[sid] ?? []).length > 0) return {};
      return {
        messagesBySession: { ...s.messagesBySession, [sid]: history.map(toChatMessage) },
        historyTotalBySession: { ...s.historyTotalBySession, [sid]: total },
      };
    });
  },
  loadMoreHistory: async (sid) => {
    // The offset is however many the client already holds. The backend counts
    // back from the newest message, so that lands exactly before the oldest one
    // on screen -- and a message arriving mid-fetch cannot shift the window.
    const loaded = (get().messagesBySession[sid] ?? []).length;
    const { messages: older, total } = await api.getMessages(sid, {
      limit: PAGE_SIZE,
      offset: loaded,
    });
    set((s) => ({
      messagesBySession: {
        ...s.messagesBySession,
        [sid]: [...older.map(toChatMessage), ...(s.messagesBySession[sid] ?? [])],
      },
      historyTotalBySession: { ...s.historyTotalBySession, [sid]: total },
    }));
  },
}));
