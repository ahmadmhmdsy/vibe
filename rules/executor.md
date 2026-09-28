---
id: executor
status: active
scope: services/vibe executor
applies_when: executor, preview, dev server, or subprocess work
owner: repository-owner
last_reviewed: 2026-09-28
supersedes: none
evidence: design spec §6, §9
---

# Executor rules

- The executor is a **seam**: `LocalSubprocessExecutor` today,
  `DockerExecutor` at M4 — same interface, no agent-tool changes.
- Command allowlist: only `pnpm install`, `vite build`, `vite dev` with
  fixed flags. No arbitrary shell.
- Every tool has a timeout and output truncation; the dev server has an
  idle timeout and is killed on session delete.
- Ports are allocated from a fixed local range; process cleanup is
  guaranteed on backend shutdown.
- Console + screenshot capture goes through the headless Chromium
  (Playwright); the same feed serves the auto-run loop and the UI console
  tab.
