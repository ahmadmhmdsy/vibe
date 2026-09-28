---
id: evidence
status: active
scope: repository-wide
applies_when: claiming any result, metric, or validation
owner: repository-owner
last_reviewed: 2026-09-28
supersedes: none
evidence: AGENTS.md validation rules
---

# Evidence rules

- Validation labels: `PASS`, `FAIL`, `SKIPPED`, `BLOCKED`,
  `NEEDS_USER_DECISION`. That list is the single vocabulary.
- Evidence is an exact relative artifact path (test output, log file,
  build report, git commit) — never a remembered number, never
  console-only.
- Smallest proof first: run the smallest set of checks that could prove
  the claim false.
- No test/timing/count claims belong in static files: discover them from
  the suites.
- Honest labels over optimistic claims; a limitation reported is worth
  more than a green check.
