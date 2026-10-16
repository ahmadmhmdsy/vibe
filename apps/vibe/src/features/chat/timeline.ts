// features/chat/timeline.ts — the transcript as a fold over the session's event log.
//
// The backend already publishes everything that happens in a turn: the user
// message, each tool call and its result, the assistant's text, and errors.
// The old client threw all of it away except text_chunk and turn_complete, so a
// user watched a spinner for two minutes with no idea what the agent was doing.
// This module is the pure reducer that keeps the whole story.
//
// It is deliberately free of React and of the network so the ordering rules —
// which are subtle — can be unit tested directly.
//
// Two ordering rules matter more than the rest:
//
// 1. `text_chunk` is ephemeral: it carries `event_log.next_seq(sid)`, a seq
//    RESERVED (and advanced) from the same counter the stored events draw from,
//    but never written to the log. Because the chunks step that counter, the
//    stored events of one turn come from a window the chunks passed through, so
//    the client must only advance `lastSeq` on a STORED event — treating a
//    chunk's seq as a dedup watermark can drop the message the chunks fill.
// 2. The assistant/message that follows a run of text chunks is authoritative:
//    it FINALIZES the bubble the chunks were filling rather than appending a
//    second one. A tool call closes the open bubble for the same reason — text
//    before a tool call and text after it are two separate paragraphs.

import { EPHEMERAL_EVENT_TYPES, type StreamEvent } from "../../lib/sse";

export type ToolStatus = "running" | "ok" | "error";
export type NoticeTone = "info" | "warning";

export interface UserItem {
  kind: "user";
  id: string;
  seq: number;
  content: string;
  /** True while this is only the client's optimistic copy. A matching
   *  user/message from the server confirms it instead of duplicating it. */
  pending: boolean;
}

export interface AssistantItem {
  kind: "assistant";
  id: string;
  seq: number;
  content: string;
  streaming: boolean;
}

export interface ErrorItem {
  kind: "error";
  id: string;
  seq: number;
  content: string;
}

export interface ToolItem {
  kind: "tool";
  id: string;
  seq: number;
  /** The backend's tool_call id, used to pair the result with the call. */
  callId: string;
  name: string;
  args: unknown;
  status: ToolStatus;
  result?: string;
  startedAt: number;
  finishedAt?: number;
}

export interface NoticeItem {
  kind: "notice";
  id: string;
  seq: number;
  content: string;
  tone: NoticeTone;
}

export type TimelineItem = UserItem | AssistantItem | ErrorItem | ToolItem | NoticeItem;

export interface TimelineState {
  items: TimelineItem[];
  /** Highest seq among STORED events folded in. Ephemeral events never move it. */
  lastSeq: number;
  /** The assistant item currently receiving streamed text, if any. */
  streamingId: string | null;
  /** tool_call id -> the tool item that renders it. */
  toolItemByCallId: Record<string, string>;
}

export function emptyTimeline(): TimelineState {
  return { items: [], lastSeq: 0, streamingId: null, toolItemByCallId: {} };
}

let itemCounter = 0;

/** Monotonic per page load. The id only has to be unique within one timeline,
 *  which is what lets React key on it instead of on the array index. */
export function nextItemId(prefix: string): string {
  itemCounter += 1;
  return `${prefix}-${itemCounter}`;
}

/** Only for tests: makes generated ids predictable again. */
export function resetItemIds(): void {
  itemCounter = 0;
}

const asString = (value: unknown, fallback = ""): string =>
  typeof value === "string"
    ? value
    : value === undefined || value === null
      ? fallback
      : String(value);

const asNumber = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

/** Stop treating the open assistant bubble as live. Called whenever something
 *  arrives that proves the model has moved on. */
function closeStream(state: TimelineState): TimelineState {
  if (!state.streamingId) return state;
  return {
    ...state,
    streamingId: null,
    items: state.items.map((item) =>
      item.id === state.streamingId && item.kind === "assistant"
        ? { ...item, streaming: false }
        : item
    ),
  };
}

/** Fold one streamed event into the timeline.
 *
 * `now` is injectable so tool durations are testable without fake timers. */
export function applyEvent(
  state: TimelineState,
  event: StreamEvent,
  now = Date.now()
): TimelineState {
  const seq = asNumber(event.seq) ?? 0;
  const ephemeral = EPHEMERAL_EVENT_TYPES.has(event.type);

  // Replay overlap on reconnect: a stored event already folded is skipped.
  if (!ephemeral && seq > 0 && seq <= state.lastSeq) return state;

  const stored = <T extends TimelineState>(next: T): T => ({ ...next, lastSeq: seq });

  switch (event.type) {
    case "text_chunk": {
      const text = asString(event.payload.text);
      if (!text) return state;
      const openId = state.streamingId;
      const open = openId ? state.items.find((item) => item.id === openId) : undefined;
      if (open && open.kind === "assistant") {
        return {
          ...state,
          items: state.items.map((item) =>
            item.id === open.id && item.kind === "assistant"
              ? { ...item, content: item.content + text }
              : item
          ),
        };
      }
      const id = nextItemId("assistant");
      return {
        ...state,
        streamingId: id,
        items: [...state.items, { kind: "assistant", id, seq, content: text, streaming: true }],
      };
    }

    case "user/message": {
      const content = asString(event.payload.content);
      // Confirm the optimistic copy the composer already rendered.
      for (let index = state.items.length - 1; index >= 0; index -= 1) {
        const item = state.items[index];
        if (item.kind === "user" && item.pending && item.content === content) {
          const items = state.items.slice();
          items[index] = { ...item, seq, pending: false };
          return stored({ ...state, items });
        }
      }
      const id = nextItemId("user");
      return stored({
        ...state,
        items: [...state.items, { kind: "user", id, seq, content, pending: false }],
      });
    }

    case "assistant/message": {
      const content = asString(event.payload.content);
      const closed = closeStream(state);
      // If a bubble was open, this stored message is its authoritative text.
      if (state.streamingId) {
        return stored({
          ...closed,
          items: closed.items.map((item) =>
            item.id === state.streamingId && item.kind === "assistant"
              ? { ...item, content, streaming: false }
              : item
          ),
        });
      }
      const id = nextItemId("assistant");
      return stored({
        ...closed,
        items: [...closed.items, { kind: "assistant", id, seq, content, streaming: false }],
      });
    }

    case "assistant/error": {
      const content = asString(event.payload.content, "The model returned an error.");
      const id = nextItemId("error");
      // closeStream returns a NEW items array with streaming cleared. Appending
      // to state.items here would throw that array away and leave the open
      // assistant bubble with streaming: true, so its caret never stopped and
      // the next chunk opened a second bubble.
      const closed = closeStream(state);
      return stored({ ...closed, items: [...closed.items, { kind: "error", id, seq, content }] });
    }

    case "tool_call": {
      const call = (event.payload.tool_call ?? {}) as Record<string, unknown>;
      const callId = asString(call.id, `call-${seq}`);
      const name = asString(call.name, "tool");
      const id = nextItemId("tool");
      // Text before a tool call is finished text.
      const closed = closeStream(state);
      return stored({
        ...closed,
        items: [
          ...closed.items,
          {
            kind: "tool",
            id,
            seq,
            callId,
            name,
            args: call.args ?? {},
            status: "running",
            startedAt: now,
          },
        ],
        toolItemByCallId: { ...state.toolItemByCallId, [callId]: id },
      });
    }

    case "tool_result": {
      const callId = asString(event.payload.tool_call_id);
      const result = asString(event.payload.content);
      const status: ToolStatus = event.payload.is_error ? "error" : "ok";
      const itemId = state.toolItemByCallId[callId];

      if (itemId) {
        return stored({
          ...state,
          items: state.items.map((item) =>
            item.id === itemId && item.kind === "tool"
              ? { ...item, status, result, finishedAt: now }
              : item
          ),
        });
      }

      // A result whose call was never seen — a session opened mid-turn, or a
      // call the log predates. Showing the result alone beats dropping it.
      const id = nextItemId("tool");
      return stored({
        ...state,
        items: [
          ...state.items,
          {
            kind: "tool",
            id,
            seq,
            callId,
            name: asString(event.payload.name, "tool"),
            args: {},
            status,
            result,
            startedAt: now,
            finishedAt: now,
          },
        ],
      });
    }

    case "turn_complete": {
      const closed = closeStream(state);
      if (!event.payload.aborted) return stored(closed);
      const id = nextItemId("notice");
      return stored({
        ...closed,
        items: [...closed.items, { kind: "notice", id, seq, content: "Stopped.", tone: "warning" }],
      });
    }

    case "turn/aborted":
      return stored(closeStream(state));

    case "error": {
      const content = asString(event.payload.message, "Something went wrong.");
      const id = nextItemId("error");
      // Same trap as assistant/error above: append to the closed array.
      const closed = closeStream(state);
      return stored({
        ...closed,
        items: [...closed.items, { kind: "error", id, seq, content }],
      });
    }

    default:
      // Unknown event types are ignored rather than rendered as noise, but the
      // cursor still advances so a replay cannot loop on them.
      return stored(state);
  }
}

/** Fold a whole replayed log in one pass. */
export function applyEvents(state: TimelineState, events: readonly StreamEvent[]): TimelineState {
  return events.reduce((acc, event) => applyEvent(acc, event), state);
}

export interface OptimisticUser {
  id: string;
  content: string;
}

/** Append the composer's optimistic user message. The matching user/message
 *  event confirms it; if the send fails the caller removes it by id. */
export function addOptimisticUser(state: TimelineState, content: string): TimelineState {
  const id = nextItemId("user");
  return {
    ...state,
    items: [...state.items, { kind: "user", id, seq: 0, content, pending: true }],
  };
}

export function removeItem(state: TimelineState, id: string): TimelineState {
  if (!state.items.some((item) => item.id === id)) return state;
  return { ...state, items: state.items.filter((item) => item.id !== id) };
}
