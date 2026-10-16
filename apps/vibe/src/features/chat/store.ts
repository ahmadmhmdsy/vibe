// features/chat/store.ts — chat state.
//
// The transcript is an event log, not a list the client patches piecemeal: the
// composer adds one optimistic row, the SSE stream folds every published event
// through the pure reducer in ./timeline, and opening a session replays the
// server's log so the whole turn — tool calls included — is on screen.
// Everything else here (streaming latch, stop latch, drafts, model) is small
// per-session bookkeeping around that.

import { create } from "zustand";
import {
  addOptimisticUser,
  applyEvent,
  emptyTimeline,
  removeItem,
  type TimelineState,
} from "./timeline";
import type { StreamEvent } from "../../lib/sse";

/** A one-shot text handoff to a session's composer. The id makes each handoff
 * distinguishable from one the composer already adopted, which is what lets the
 * composer adopt it during render rather than in an effect. */
export interface PendingDraft {
  id: number;
  text: string;
}

/** Monotonic within a page load; the id only has to order handoffs. */
let draftCounter = 0;

/**
 * One shared empty timeline.
 *
 * A zustand selector must return a stable reference or the component re-renders
 * on every unrelated store read, so selectors fall back to this constant rather
 * than calling emptyTimeline() themselves. Nothing mutates it: every reducer
 * call returns a new state object.
 */
export const EMPTY_TIMELINE: TimelineState = emptyTimeline();

interface ChatState {
  /** The folded transcript per session, keyed by session id. */
  timelineBySession: Record<string, TimelineState>;
  isStreamingBySession: Record<string, boolean>;
  stopRequested: Record<string, boolean>;
  model: { provider_id: string; model_id: string };
  setModel: (m: { provider_id: string; model_id: string }) => void;
  /** A draft handed to a session by something other than typing — today, the
   * first-run example prompts. Consumed once, so a remount cannot refill a box
   * the user already cleared or sent. */
  pendingDraftBySession: Record<string, PendingDraft>;
  setPendingDraft: (sid: string, text: string) => void;
  takePendingDraft: (sid: string) => PendingDraft | undefined;
  /** Fold one streamed event into a session's transcript. */
  applyStreamEvent: (sid: string, event: StreamEvent) => void;
  /** Drop a session's transcript. Called before an SSE replay from seq 0 so a
   * session switch cannot blend two logs into one list. */
  resetTimeline: (sid: string) => void;
  /** Add the composer's optimistic user message and return its item id, so the
   * caller can withdraw exactly that row if the send fails. */
  addOptimisticUserMessage: (sid: string, content: string) => string;
  /** Withdraw one timeline item by id. */
  removeTimelineItem: (sid: string, id: string) => void;
  beginStream: (sid: string) => void;
  endStream: (sid: string) => void;
  requestStop: (sid: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  timelineBySession: {},
  isStreamingBySession: {},
  stopRequested: {},
  model: { provider_id: "opencode-go", model_id: "kimi-k3" },
  setModel: (model) => set({ model }),
  pendingDraftBySession: {},
  setPendingDraft: (sid, text) =>
    set((s) => ({
      pendingDraftBySession: { ...s.pendingDraftBySession, [sid]: { id: ++draftCounter, text } },
    })),
  takePendingDraft: (sid) => {
    const draft = get().pendingDraftBySession[sid];
    if (draft === undefined) return undefined;
    set((s) => {
      const next = { ...s.pendingDraftBySession };
      delete next[sid];
      return { pendingDraftBySession: next };
    });
    return draft;
  },
  applyStreamEvent: (sid, event) =>
    set((s) => {
      const current = s.timelineBySession[sid] ?? EMPTY_TIMELINE;
      const next = applyEvent(current, event);
      // A replayed duplicate or an empty chunk leaves the reducer's state object
      // identical; skipping the store write keeps subscribers from re-rendering.
      if (next === current) return {};
      return { timelineBySession: { ...s.timelineBySession, [sid]: next } };
    }),
  resetTimeline: (sid) =>
    set((s) => ({ timelineBySession: { ...s.timelineBySession, [sid]: emptyTimeline() } })),
  addOptimisticUserMessage: (sid, content) => {
    const current = get().timelineBySession[sid] ?? EMPTY_TIMELINE;
    const next = addOptimisticUser(current, content);
    const added = next.items[next.items.length - 1];
    set((s) => ({ timelineBySession: { ...s.timelineBySession, [sid]: next } }));
    return added.id;
  },
  removeTimelineItem: (sid, id) =>
    set((s) => {
      const current = s.timelineBySession[sid] ?? EMPTY_TIMELINE;
      const next = removeItem(current, id);
      if (next === current) return {};
      return { timelineBySession: { ...s.timelineBySession, [sid]: next } };
    }),
  beginStream: (sid) =>
    set((s) => ({
      isStreamingBySession: { ...s.isStreamingBySession, [sid]: true },
      // The stop latch is per-turn: the next turn must not inherit it.
      stopRequested: { ...s.stopRequested, [sid]: false },
    })),
  endStream: (sid) =>
    set((s) => ({ isStreamingBySession: { ...s.isStreamingBySession, [sid]: false } })),
  requestStop: (sid) => set((s) => ({ stopRequested: { ...s.stopRequested, [sid]: true } })),
}));
