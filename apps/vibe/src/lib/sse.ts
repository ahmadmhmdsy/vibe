// lib/sse.ts — Server-Sent Events client with exponential backoff.
// Handles connection, parsing, and automatic reconnection.

import { API_BASE } from "./api";

export interface StreamEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}

/** Event types the server streams but never writes to the event log.
 *
 * They still consume a sequence number: `EventLog.next_seq` reserves one
 * (it increments the counter) so that a client always has a monotonic value
 * to resume from. The next *stored* event therefore gets a strictly higher
 * seq, which is why the resume cursor may safely advance past these.
 *
 * Callers use this set to decide what may become a durable timeline item,
 * not to hold the resume cursor back. */
export const EPHEMERAL_EVENT_TYPES: ReadonlySet<string> = new Set(["text_chunk"]);

/** Connection state the UI can render.
 *
 * "lost" is the state the client used to enter silently: after
 * maxReconnectAttempts the old code simply stopped scheduling retries, so the
 * chat still looked live while it received nothing. A caller that renders this
 * can tell the user, and a lost connection can be resumed from lastSeq.
 */
export type StreamStatus = "idle" | "open" | "reconnecting" | "lost";

export class SSEClient {
  lastSeq = 0;
  status: StreamStatus = "idle";
  private source: EventSource | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private baseReconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;
  private sessionId = "";
  private onEvent: ((e: StreamEvent) => void) | null = null;
  private onStatus: ((s: StreamStatus) => void) | null = null;

  /** baseUrl defaults to the single API base in ./api.
   *
   * Passing one is only for tests; a caller that builds its own origin is how
   * the chat stream and the REST client drifted apart in the first place.
   */
  constructor(private baseUrl: string = API_BASE) {}

  private setStatus(status: StreamStatus): void {
    this.status = status;
    this.onStatus?.(status);
  }

  parse(raw: string): StreamEvent | null {
    // EventSource's onmessage delivers the data field with the `data: `
    // prefix and the trailing blank line already stripped; accept raw
    // `data: ...\n\n` frames too.
    const match = raw.match(/data: (.+)\n\n/);
    const json = match ? match[1] : raw;
    try {
      const event = JSON.parse(json) as StreamEvent;
      // Only advance on a strictly newer seq: a replayed or re-published frame
      // must not move the resume cursor backwards, or the reconnect re-delivers
      // everything after it.
      //
      // Ephemeral events advance the cursor too. EventLog.next_seq reserves a
      // number rather than peeking at one, so the next stored event is strictly
      // higher and nothing is skipped; holding the cursor back instead made
      // every reconnect replay and re-render the chunks already shown.
      if (typeof event.seq === "number" && event.seq > this.lastSeq) {
        this.lastSeq = event.seq;
      }
      return event;
    } catch {
      return null;
    }
  }

  connect(
    sessionId: string,
    onEvent: (e: StreamEvent) => void,
    onStatus?: (s: StreamStatus) => void
  ): void {
    this.intentionallyClosed = false;
    this.reconnectAttempts = 0;
    this.sessionId = sessionId;
    this.onEvent = onEvent;
    this.onStatus = onStatus ?? null;
    this.open(sessionId, onEvent);
  }

  /** Resume a connection that reached "lost".
   *
   * Reset the attempt budget and open again from lastSeq, so the replay
   * continues exactly where the client stopped receiving.
   */
  retry(): void {
    if (this.intentionallyClosed) return;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
    this.setStatus("reconnecting");
    this.open(this.sessionId, this.onEvent ?? (() => {}));
  }

  private open(sessionId: string, onEvent: (e: StreamEvent) => void): void {
    if (this.intentionallyClosed) return;

    this.source = new EventSource(
      `${this.baseUrl}/sessions/${sessionId}/events?after_seq=${this.lastSeq}`
    );

    this.source.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus("open");
    };

    this.source.onmessage = (msg) => {
      const event = this.parse(msg.data);
      if (event) {
        this.reconnectAttempts = 0;
        // A test double may never fire onopen; a delivered frame is proof the
        // stream is live, so recover the status here too.
        if (this.status !== "open") this.setStatus("open");
        onEvent(event);
      }
    };

    this.source.onerror = () => {
      this.source?.close();
      if (this.intentionallyClosed) return;

      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.setStatus("reconnecting");
        const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => {
          this.open(sessionId, onEvent);
        }, delay);
      } else {
        // Out of retries. Say so instead of going quiet.
        this.setStatus("lost");
      }
    };
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    this.setStatus("idle");
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.source?.close();
    this.source = null;
  }
}
