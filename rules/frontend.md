---
id: frontend
status: active
scope: apps/vibe
applies_when: frontend React or TypeScript work
owner: repository-owner
last_reviewed: 2026-09-30
supersedes: none
evidence: design spec §8
---

# Frontend rules

- Feature modules own their state (a zustand store), components, and API
  calls. The app root composes them — removing a feature means removing
  its module from the composition.
- The chat module never imports the preview module; both talk to the
  backend through `lib/`.
- Function components + hooks only; typed props; co-located styles.
- The frontend sees only provider names, model labels, and masked key
  status — never API keys or base URLs.
- SSE is the live channel: the chat UI renders from the EventLog plus the
  live stream; on reconnect, replay from the last-seen seq.
- SSE clients are tested against the real `EventSource` data shape:
  `onmessage` delivers `msg.data` with the `data: ` prefix and the
  trailing blank line already stripped. A unit test that feeds raw
  `data: ...\n\n` frames to the parser certifies nothing about the live
  path — test the shape the browser actually delivers. A parse that returns
  null on unrecognized input must be a tested path, never a silent drop.
- "The agent responded" is verified in the browser DOM (the reply renders
  in the chat), never only by a 200 from the send call or a persisted
  message — the chat UI renders exclusively from the SSE stream.
- Accessibility is part of correctness: semantic HTML, labels on inputs,
  keyboard reachability.
