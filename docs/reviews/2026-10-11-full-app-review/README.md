# Full app review — Vibe Coding App (2026-10-11)

**Reviewer:** DSH agent session, 2026-10-11
**Subject:** the whole product — backend (`services/vibe`), frontend
(`apps/vibe`), and the repository's own truth-telling.
**Posture:** read-only review plus additive artifacts. No application file was
modified; the only files written are inside this directory.

## Why this exists

The repository is well documented, but documentation drifts. This review
re-establishes the *current* truth from source artifacts — running code,
executed suites, and probes that exercise production paths — and records both
what is strong and what is broken. Each finding carries an exact location, a
reproduction, and raw evidence.

## Method

1. Read the authority chain: `AGENTS.md` → `SOUL.md` → `CURRENT_STATE.md` →
   `TASKS.md` → `HANDOFF.md` → the design spec.
2. Read every backend source module and the frontend feature modules.
3. Ran the declared suites (pytest, ruff, vitest, tsc, eslint, prettier, build)
   and stored the raw output under `evidence/`.
4. Wrote executable probes under `probes/` for each suspected defect and ran
   them against the real FastAPI app / real executor. A finding is only filed
   here once a probe or the suite output shows it.
5. Documented as I went (this file plus the numbered finding files).

## Severity legend

| Label | Meaning |
|---|---|
| **Critical** | Data loss, remote exploit, or the product's core loop is broken. |
| **High** | A real defect a user or attacker can hit in normal use. |
| **Medium** | Correctness/resource/robustness defect with real but bounded impact. |
| **Low** | Contract inconsistency, dead code, or hygiene. |
| **Info** | Observation, not a defect. |

## Status

| File | Area | State |
|---|---|---|
| [01-baseline-validation.md](./01-baseline-validation.md) | Suites and checks as of 2026-10-11 | complete |
| [02-backend-findings.md](./02-backend-findings.md) | API contract, security, runtime, executor, lifecycle, observability | complete (first pass) |
| [03-frontend-findings.md](./03-frontend-findings.md) | React app, stores, SSE client, UX/a11y | complete (static; not probe-run) |
| [04-docs-and-process.md](./04-docs-and-process.md) | Documentation drift, CI, tests | complete |
| [FINDINGS.md](./FINDINGS.md) | Consolidated register of every finding | live — 48 findings (24 backend, 16 frontend, 8 docs/CI/tests) |

### Raw evidence

- `evidence/baseline-pytest.txt`, `baseline-ruff.txt`
- `evidence/baseline-vitest.txt`, `baseline-typecheck.txt`,
  `baseline-eslint.txt`, `baseline-format.txt`, `baseline-build.txt`
- `evidence/backend-probe.txt`

### Probes (re-runnable)

- `probes/backend_probe.py` — seven probes (API validation, allowlist, memory,
  race, timeout, logging, delete).
- `probes/custom_provider_probe.py` — four probes over the custom-provider store.
- `probes/file_count_probe.py` — the workspace walk against the real E2E workspace.
- Run any of them with
  `services\vibe\.venv\Scripts\python.exe ..\..\docs\reviews\2026-10-11-full-app-review\probes\<name>.py`
  from `services/vibe`. All three use temp directories except the read-only
  file-count check.

## Headline

The engineering discipline in this repository is unusually high: a real
composition root, explicit seams, an error taxonomy, a sqlite event log, a
delete cascade, and tests that assert observable behaviour rather than
implementation. The defects found are mostly at the *edges* — inputs that
were never validated, a guard that is checked but not claimed atomically, a
timeout that returns without killing its child, and a logging call that
cannot format. None of them are visible from the green suite, which is the
point of probing.
