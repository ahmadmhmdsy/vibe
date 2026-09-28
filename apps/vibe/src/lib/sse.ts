export interface StreamEvent {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}

export class SSEClient {
  lastSeq = 0;
  private source: EventSource | null = null;
  constructor(private baseUrl: string) {}

  parse(raw: string): StreamEvent | null {
    const match = raw.match(/data: (.+)\n\n/);
    if (!match) return null;
    const event = JSON.parse(match[1]) as StreamEvent;
    this.lastSeq = event.seq;
    return event;
  }

  connect(sessionId: string, onEvent: (e: StreamEvent) => void): void {
    this.source = new EventSource(`${this.baseUrl}/sessions/${sessionId}/events?after_seq=${this.lastSeq}`);
    this.source.onmessage = (msg) => {
      const event = this.parse(msg.data);
      if (event) onEvent(event);
    };
    this.source.onerror = () => {
      this.source?.close();
      setTimeout(() => this.connect(sessionId, onEvent), 1000);
    };
  }

  disconnect(): void {
    this.source?.close();
    this.source = null;
  }
}
