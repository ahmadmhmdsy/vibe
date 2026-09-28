---
id: frontend
status: active
scope: apps/vibe
applies_when: frontend React or TypeScript work
owner: repository-owner
last_reviewed: 2026-09-28
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
- Accessibility is part of correctness: semantic HTML, labels on inputs,
  keyboard reachability.
