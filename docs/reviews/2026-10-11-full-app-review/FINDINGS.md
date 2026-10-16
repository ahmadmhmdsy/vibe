# FINDINGS — consolidated register (2026-10-11)

One row per finding. Detail lives in the numbered files; status is `open` unless
a later entry says otherwise. This review changed **no application code** — it
only added files under `docs/reviews/2026-10-11-full-app-review/`.

Severity legend: [README.md](./README.md). Probes:
`probes/backend_probe.py` (7 defects) and `probes/custom_provider_probe.py`
(4 more), both re-runnable against temp directories only.

## Backend — [02-backend-findings.md](./02-backend-findings.md)

| ID | Sev | Area | Finding | Detail |
|---|---|---|---|---|
| BE-01 | High | API contract | `body: dict` means malformed requests answer 500, not 4xx | [02](./02-backend-findings.md) §BE-01 |
| BE-02 | High | Security / supply chain | allowlist bypassed by `react@npm:evil-package` and similar specs | [02](./02-backend-findings.md) §BE-02 |
| BE-03 | High | Agent runtime / product | no conversation memory: only the newest user message reaches the model | [02](./02-backend-findings.md) §BE-03 |
| BE-04 | High | Concurrency | the "one run per session" 409 guard is not atomic — two sends both run | [02](./02-backend-findings.md) §BE-04 |
| BE-05 | Medium | Executor / resources | a timed-out command is never killed and keeps running | [02](./02-backend-findings.md) §BE-05 |
| BE-06 | Medium | Lifecycle / data | a failed workspace move deletes the transcript but keeps the session | [02](./02-backend-findings.md) §BE-06 |
| BE-07 | Medium | Observability | the VIBE_HOST warning raises a TypeError and is never emitted | [02](./02-backend-findings.md) §BE-07 |
| BE-08 | Medium | Agent runtime / logging | auto-run fix turns are neither logged nor broadcast | [02](./02-backend-findings.md) §BE-08 |
| BE-09 | Low | Tools | "no browser driver" is reported when the cause is "no dev server" | [02](./02-backend-findings.md) §BE-09 |
| BE-10 | Low | API contract | dead `usage is None` check; get-session omits timestamps; raw error text leaks | [02](./02-backend-findings.md) §BE-10 |
| BE-11 | Low | Lifecycle / disk | `.trash/` has no retention policy | [02](./02-backend-findings.md) §BE-11 |
| BE-12 | Low | Performance | pagination and usage scan the whole event log per request | [02](./02-backend-findings.md) §BE-12 |
| BE-13 | Low/Info | Config | import-time `.env` walk up three parent dirs mutates `os.environ` | [02](./02-backend-findings.md) §BE-13 |
| BE-14 | Medium | Providers / API | one custom model without an `id` breaks `GET /catalog` (500) for the whole app | [02](./02-backend-findings.md) §BE-14 |
| BE-15 | Medium | Providers / durability | a corrupt `providers.json` 500s `/providers` and `/catalog` with no recovery | [02](./02-backend-findings.md) §BE-15 |
| BE-16 | Low | Providers / concurrency | the provider store blocks the event loop and loses concurrent writes | [02](./02-backend-findings.md) §BE-16 |
| BE-17 | Info | Providers / API | the API can clear a key (`apiKey: ""`); only the UI cannot | [02](./02-backend-findings.md) §BE-17 |
| BE-18 | Info | Secrets | provider keys are plaintext at the workspace root, but agent-confined | [02](./02-backend-findings.md) §BE-18 |
| BE-19 | Medium | Agent runtime | the agent is given no system prompt at all: its whole instruction set is the tool schemas | [02](./02-backend-findings.md) §BE-19 |
| BE-20 | Medium | Lifecycle / API contract | a workspace held open by another process makes `DELETE /sessions/{sid}` answer 500 and hides that the session survived | [02](./02-backend-findings.md) §BE-20 |
| BE-21 | Medium | Operations / logging | the rotating log file is never written unless the user names one: an unset `VIBE_LOG_FILE` counted as "off", so the documented default path did not exist | [02](./02-backend-findings.md) §BE-21 |
| BE-22 | High | Agent runtime / event log | a second event-log allocator on one session makes `POST /messages` a 500: the seq counter is seeded once from `MAX(seq)`, so a rival writer's row makes the loser's INSERT raise `IntegrityError` mid-turn | [02](./02-backend-findings.md) `BE-22 |
| BE-23 | High | Operations / API contract | in `prod` mode the UI's own origin is refused, so no session can be created: the guard trusted only the dev Vite origins | [02](./02-backend-findings.md) §BE-23 |
| BE-24 | Low | CLI / docs | `vibe --help` promised `repair` would quarantine anything unreadable, but it deliberately leaves a corrupt database in place (only an unreadable providers file is moved aside) | [02](./02-backend-findings.md) §BE-24 |

## Frontend — [03-frontend-findings.md](./03-frontend-findings.md)

| ID | Sev | Area | Finding | Detail |
|---|---|---|---|---|
| FE-01 | Medium | SSE | the event stream dies silently after 5 reconnect attempts, with no UI state | [03](./03-frontend-findings.md) §FE-01 |
| FE-02 | Medium | Code panel/store | a dead backend renders as "No files yet" / an empty file, never an error | [03](./03-frontend-findings.md) §FE-02 |
| FE-03 | Medium | Model picker | model ids containing "/" are truncated by `split("/")` | [03](./03-frontend-findings.md) §FE-03 |
| FE-04 | Medium | Chat UX | auto-scroll yanks a user reading history to the bottom on every chunk | [03](./03-frontend-findings.md) §FE-04 |
| FE-05 | Medium | Code panel | Monaco never gets a theme, so it renders light inside the dark app | [03](./03-frontend-findings.md) §FE-05 |
| FE-06 | Low | Preview store | global preview state bleeds the previous session's URL/status | [03](./03-frontend-findings.md) §FE-06 |
| FE-07 | Low | Approvals | a failed approve/deny is swallowed; the card silently reappears | [03](./03-frontend-findings.md) §FE-07 |
| FE-08 | Low | Approvals | `savePolicy` writes localStorage unguarded while `loadPolicy` is guarded | [03](./03-frontend-findings.md) §FE-08 |
| FE-09 | Low | Shell | the palette advertises Cmd+N but no such shortcut is bound | [03](./03-frontend-findings.md) §FE-09 |
| FE-10 | Low | Composer | the over-limit branch is dead because `maxLength` caps input | [03](./03-frontend-findings.md) §FE-10 |
| FE-11 | Low | Composer | a failed send keeps the optimistic user bubble, so a retry duplicates it | [03](./03-frontend-findings.md) §FE-11 |
| FE-12 | Low | Shell | no error boundary around the chat/sessions panels or at the root | [03](./03-frontend-findings.md) §FE-12 |
| FE-13 | Low | Hooks | four always-on polling loops with no visibility gate or success backoff | [03](./03-frontend-findings.md) §FE-13 |
| FE-14 | Low | A11y | nested live regions double-announce streaming text and toasts | [03](./03-frontend-findings.md) §FE-14 |
| FE-15 | Low/Info | Docs/tests | logger comment; `getSession` type lies; theme toggle edge; key cannot be cleared; test gaps | [03](./03-frontend-findings.md) §FE-15 |
| FE-16 | Low | Chat | "Jump to latest" is offered when the transcript fits its box and cannot scroll, because visibility was gated on a flag only `onScroll` updated | [03](./03-frontend-findings.md) §FE-16 |

## Docs, process, tests — [04-docs-and-process.md](./04-docs-and-process.md)

| ID | Sev | Area | Finding | Detail |
|---|---|---|---|---|
| DOC-01 | Medium | Docs / CI | `format:check` fails on the current worktree while two docs say it passes | [04](./04-docs-and-process.md) §DOC-01 |
| DOC-02 | Low | Docs | `CURRENT_STATE.md` Git section is stale (HEAD and dirty count) | [04](./04-docs-and-process.md) §DOC-02 |
| DOC-03 | Low | Docs | the state files disagree on the frontend test count | [04](./04-docs-and-process.md) §DOC-03 |
| DOC-04 | Low | Docs | a listed "open finding" (3680 paths) is already fixed — verified 10 paths | [04](./04-docs-and-process.md) §DOC-04 |
| DOC-05 | Low | CI | CI is unverified; its cache path points at a lockfile the root workspace no longer uses | [04](./04-docs-and-process.md) §DOC-05 |
| DOC-06 | Info | Docs | the review artifacts are outside AGENTS.md's document map | [04](./04-docs-and-process.md) §DOC-06 |
| DOC-07 | Low | Docs | `ENVIRONMENT.md` says Playwright capture was REMOVED; the driver and the dependency are both present | [04](./04-docs-and-process.md) §DOC-07 |
| TEST-01 | Low | Tests | pytest leaves two subprocess resource warnings | [04](./04-docs-and-process.md) §TEST-01 |

## Counts

- Backend: 6 High, 9 Medium, 6 Low, 1 Info/Low-Info, 2 Info.
- Frontend: 5 Medium, 11 Low/Low-Info.
- Docs/CI/tests: 1 Medium, 6 Low, 1 Info (DOC-07 was added by the hardening plan's R0-T1; BE-19 was added by R3-T4).
- Total: 48 findings — 24 backend, 16 frontend, 8 docs/CI/tests (BE-20, BE-21, BE-22 and BE-23 were found by the R7 release verification and its first real browser run, BE-24 by the CLI smoke alongside it, and FE-16 by the browser re-check; all fixed in the same phase; BE-22 came out of the run whose traceback BE-21's missing log had been hiding).

## Suggested order of work

1. **Correctness under concurrency and cancellation:** BE-04, BE-05, BE-06.
2. **The security and contract edges:** BE-02, BE-01, BE-14, BE-15.
3. **The product gap:** BE-03 (history) then BE-08 (make fix turns visible).
4. **Frontend trust:** FE-02, FE-01, FE-03, FE-05, FE-04.
5. **Docs truth:** DOC-01, DOC-02, DOC-04, then register the review (DOC-06).
