# Publishing the public repository

[vibe](https://github.com/ahmadmhmdsy/vibe) is public. This checkout is where
the work happens, and it is not the same repository: the public one is
published from a clone with the vendored third-party skill packs and the
internal working files stripped out of every commit. The two histories are
built from the same commits but are not the same commits, and they are never
mixed.

One script does the publish, and it is the only supported way to do it. This
guide explains what it strips, what it checks, and what to verify afterwards.

## 1. Two repositories, one source of truth

| | this checkout | the public repository |
|---|---|---|
| where | this working tree | https://github.com/ahmadmhmdsy/vibe |
| history | every commit, including `.agents/` and `.superpowers/` | the same commits, filtered |
| audience | the people building it | anyone who clones it |
| how it changes | commit here | publish from here |

The public repository is a mirror of this one, not a parallel branch of
development. Work happens here; publishing copies the result out. Never edit
files on GitHub, never push to it by hand, and never merge anything there -
the next publish replaces what is there anyway, and a hand edit would be lost
without a trace.

## 2. What is stripped, and why

| path | why it is not public |
|---|---|
| `.agents/` | Third-party skill packs cloned from upstream repositories - `skills-lock.json` names each source. Redistribution is the upstream author's decision, not ours: the vendored copies mostly carry no licence file at all, so we cannot claim the right to republish them. |
| `.superpowers/` | Internal plans, reviews and diff dumps written for this project's own working process. They are notes to ourselves, not documentation. |
| `archive/` | Scratch scripts and a superseded screenshot from earlier phases. Kept locally for provenance, not worth publishing. |
| `skills-lock.json` | The manifest for `.agents/`. A lockfile for files that are not in the repository is misleading. |

Everything else is published: the product (`apps/`, `services/`), the docs
(`docs/`), the rules (`rules/`), the workflows (`.github/`), the launchers, and
the state documents (`AGENTS.md`, `PLAN.md`, `HANDOFF.md`, `MEMORY.md`,
`TASKS.md`, `CURRENT_STATE.md`, `ENVIRONMENT.md`).

One consequence, stated plainly: `AGENTS.md`'s portfolio table names
`.agents/skills/` as a scope. In the public copy that path does not exist, so a
reader sees a pointer to something they cannot open. It is left as is rather
than edit the router for the public view, because the two files would then
drift apart.

The strip list lives in `scripts/publish-public.ps1` (`$StripPaths`). Adding a
product path to it would delete product code from the public history on the
next publish; that list is not a place for convenience.

## 3. Publish

Prerequisites:

| need | check |
|---|---|
| Git on `PATH` | `git --version` |
| GitHub CLI, authenticated | `gh auth status` |
| `git-filter-repo` on `PATH` | `git filter-repo --version` |
| a clean working tree on `master` | `git status --short` prints nothing |

```powershell
pwsh -File scripts\publish-public.ps1 -DryRun   # preconditions and the plan; touches nothing
pwsh -File scripts\publish-public.ps1           # clone, filter, push
```

The script:

1. Refuses to start unless every precondition above holds - a dirty tree, a
   branch other than `master`, a missing tool, an unauthenticated `gh`, a
   repository that does not exist or is not public, or a destination path that
   already exists.
2. Clones this checkout with `--no-hardlinks` into a fresh directory (a
   timestamped directory under the system temp directory by default).
3. Runs `git filter-repo --force --invert-paths` over that clone for the four
   paths in section 2. The filter rewrites every commit, so the published
   history has its own SHAs.
4. Refuses to continue if any stripped path is still present in the filtered
   history - a filter that matched nothing would otherwise publish the very
   thing it exists to remove.
5. Adds `origin` (the filter removes it) and pushes `master` with
   `git push -u origin master`. There is no force flag anywhere in the script.
6. Prints the commit and file counts, and the verification commands from
   section 4.

Parameters:

| parameter | default | meaning |
|---|---|---|
| `-Repo` | `ahmadmhmdsy/vibe` | target repository, `owner/name` |
| `-Source` | the repository root | working checkout to publish from |
| `-Destination` | a timestamped directory under the system temp directory | where the filtered clone goes; an existing path is refused, never deleted |
| `-DryRun` | off | run every precondition, print the plan, stop |

The script never modifies this checkout: the clone, the filter and the push all
happen elsewhere. Repeated publishes are therefore cheap - the filter is
deterministic, so the same input produces the same commits and the push is a
fast-forward.

## 4. Verify the publish

The script prints these on success. Run them; a publish is not finished until
they answer as noted.

| check | command | expected |
|---|---|---|
| repository is public | `gh repo view ahmadmhmdsy/vibe --json visibility,defaultBranchRef,url` | `visibility: PUBLIC`, branch `master` |
| nothing stripped survived | `git -C <destination> ls-tree -r --name-only origin/master \| Select-String '^(\.agents\|\.superpowers\|archive\|skills-lock)'` | no output |
| no environment file | `git -C <destination> ls-tree -r --name-only origin/master \| Select-String '(^\|/)[.]env$'` | no output (`.env.example` is published on purpose) |
| CI is green | `gh run list --repo ahmadmhmdsy/vibe --limit 1` | `success` |
| the README images resolve | `Invoke-WebRequest 'https://raw.githubusercontent.com/ahmadmhmdsy/vibe/master/docs/assets/hero.png' -Method Head` | `200` |

The repository description and topics are GitHub settings, not part of the
history - edit them in the repository settings page if they need to change.

## 5. What never to do

- Never `git push` this checkout to the public repository. Its history
  contains `.agents/`, so the push would either be rejected as a non
  fast-forward or, with force, publish the material section 2 exists to
  exclude. The publish script is the path.
- Never force-push the public repository, in any form. If a push is rejected,
  something moved; find out what before doing anything else.
- Never rewrite this checkout's history to match the public one. The local
  history is the record of the work, including everything that stays local.
- Never filter this checkout in place (`git filter-repo` here, not on a clone).
  It rewrites the repository it is run in and drops the `origin` remote.
- Never add `.agents/` back to the published tree by editing `$StripPaths`.
- Never publish from a dirty tree, and never publish someone else's
  uncommitted work by committing it for them.
- Never put a secret in the clone by hand. `.env` is gitignored and the
  verification above greps for it; keep it that way.

## 6. When it stops

| what it says | what it means | what to do |
|---|---|---|
| `the working tree is not clean` | uncommitted or untracked paths exist | commit the work, then run again; the script does not stash or reset |
| `the working tree is on '<branch>', not 'master'` | the checkout is on a feature branch | `git switch master` |
| `the GitHub CLI is not authenticated` | `gh` has no token | `gh auth login` |
| `git-filter-repo is not on PATH` | the filter tool is missing | `uv tool install git-filter-repo` |
| `GitHub repository ... is not reachable` | wrong name, or `gh` cannot see it | `gh repo create ahmadmhmdsy/vibe --public` |
| `the destination ... already exists` | a previous clone is still there | pass a new `-Destination`, or delete the old clone yourself |
| `git push failed` | the remote moved, or credentials changed | if it was a non-fast-forward rejection, re-run from a clean `master`; never force |

Every failure exits with status 1 and pushes nothing: the clone and the filter
both finish before the push, so an aborted run leaves a directory to inspect
and the public repository untouched.
