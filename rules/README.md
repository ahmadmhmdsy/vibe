# rules/ — conditional specialist rules

Rule files here are **stable, conditional policy**. Each is loaded only
when the current task class matches its condition, never globally. Rules
never contain live truth: no PIDs, live job IDs, machine names, disk
numbers, or temporary paths — those belong to CURRENT_STATE.md.

## Layout
- One Markdown file per rule, with YAML front matter carrying: id, status,
  scope, applies_when, owner, last_reviewed, supersedes, evidence.
- rules/index.yaml is the machine-readable index (schema_version 1); it
  must list every rule file exactly once and point only to existing files.

## Editing policy
New policy rule files come from an explicitly approved authoring step,
never from an ordinary task's drive-by. Promoting a lesson candidate
into a rule requires repeated evidence plus explicit user adoption.
