// lib/sse.ts — Server-Sent Events client with exponential backoff.
// Handles connection, parsing, and automatic reconnection.

export interface StreamEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}

export class SSEClient {
  lastSeq = 0;
  private source: EventSource | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private baseReconnectDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;

  constructor(private baseUrl: string) {}

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
      if (typeof event.seq === "number" && event.seq > this.lastSeq) {
        this.lastSeq = event.seq;
      }
      return event;
    } catch {
      return null;
    }
  }

  connect(sessionId: string, onEvent: (e: StreamEvent) => void): void {
    this.intentionallyClosed = false;
    this.reconnectAttempts = 0;
    this.open(sessionId, onEvent);
  }

  private open(sessionId: string, onEvent: (e: StreamEvent) => void): void {
    if (this.intentionallyClosed) return;

    this.source = new EventSource(`${this.baseUrl}/sessions/${sessionId}/events?after_seq=${this.lastSeq}`);

    this.source.onmessage = (msg) => {
      const event = this.parse(msg.data);
      if (event) {
        this.reconnectAttempts = 0;
        onEvent(event);
      }
    };

    this.source.onerror = () => {
      this.source?.close();
      if (this.intentionallyClosed) return;

      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => {
          this.open(sessionId, onEvent);
        }, delay);
      }
    };
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.source?.close();
    this.source = null;
  }
}
