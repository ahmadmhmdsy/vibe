---
id: data
status: active
scope: workspaces and generated projects
applies_when: touching workspaces, caches, or generated projects
owner: repository-owner
last_reviewed: 2026-09-28
supersedes: none
evidence: design spec §6, §9
---

# Data rules

- Generated app projects live under `~/vibe-workspaces/<session-id>/`
  (gitignored). One directory per session.
- The agent is confined to its workspace; file tools reject paths outside.
- Session delete stops the dev server and removes the workspace — user
  confirmation required (destructive).
- The EventLog is append-only and is the source of truth for chat history,
  usage, and resume. Never rewrite or delete committed events.
- Caches (npm, build output) are regenerable — never the thing to keep.
