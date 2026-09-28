// vitest.setup.ts — jsdom does not implement EventSource; provide a no-op stub
// so components that open an SSE connection during render can be tested.
import "@testing-library/jest-dom/vitest";

class EventSourceStub {
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  constructor(public url: string) {}
  close(): void {}
}

Object.defineProperty(globalThis, "EventSource", {
  value: EventSourceStub,
  writable: true,
  configurable: true,
});
