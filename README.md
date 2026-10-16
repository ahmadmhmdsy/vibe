# vibe

A **local-first vibe-coding IDE**. Describe an app in the chat box; an agent builds it as
a multi-file React (Vite + TypeScript) project in a workspace on your machine, installs
its dependencies, builds it, runs it, and shows it in a live preview. Build errors are fed
back to the agent, which fixes them and tries again.

Everything is local: no account, no payment, no cloud service. The API listens on loopback
only, and the only outbound traffic is the LLM provider you configure - plus the package
downloads a generated app needs.

Longer walkthrough (provider keys, first app, offline, tests):
**[docs/guides/local-setup.md](docs/guides/local-setup.md)**.

## Requirements

- **Python 3.13+** - `services/vibe/pyproject.toml` requires `>=3.13`; this repo runs on
  3.13.1. The doctor treats Python 3.13 as a blocking check.
- **Node 24** - this repo runs on v24.18.0; the doctor blocks anything below Node 20.
- **pnpm 12.3.4** - pinned by `packageManager` in `package.json`; the doctor requires
  pnpm on your PATH.
- **uv 0.11.x** - creates and updates the backend venv. The doctor reports uv as an
  optional warning: once `services\vibe\.venv` exists, the app runs without it.

## Install

Run these once from the repository root. They download packages, so they need a network
connection.

```bat
cd services\vibe
uv sync --extra dev
.venv\Scripts\python.exe -m playwright install chromium
cd ..\..
pnpm install
pnpm run build
```

`pnpm run build` compiles the frontend into `apps\vibe\dist`; the one-click run below
serves that build from the backend on a single port. Without it, `start.bat` exits with
a `RuntimeError` whose message says the built frontend is missing and to run
`pnpm run build`.

Then check the machine:

```bat
doctor.bat
```

It prints one `PASS`/`FAIL` line per prerequisite and the exact fix under each failure.

## Run

**Double-click `start.bat`** (or run it from a terminal). That is the one command. It:

1. runs the doctor first and stops if a blocking check fails;
2. picks the first free port from 7321 upwards;
3. starts the backend in that window;
4. polls `http://127.0.0.1:<port>/health` until the app answers (up to 30 seconds);
5. opens your browser on the printed URL.

One window, one port. Press **Ctrl+C** there to stop everything, or run `stop.bat` from
another window: it asks the server to shut down and then checks the port is actually free
before reporting success. `stop.bat <port>` targets a different port.

`start.bat dev` keeps the development workflow: Vite serves the frontend with hot reload
on http://localhost:5173, and this window stays on the API.

## What the first run looks like

- The doctor prints its table, ending in
  `all checks passed - the app can run on this machine`.
- `start.bat` prints the mode, the API URL, the URL it will open, and how to stop.
- Once `health` answers, the browser opens the app. The server also logs to the console
  and to the workspace log:

```
vibe serving on http://127.0.0.1:7321 (prod mode, log level INFO, workspace C:\Users\<you>\vibe-workspaces)
vibe ready: workspace=C:\Users\<you>\vibe-workspaces
```

- In the app, type an idea, pick a model, and send. The first turn creates a per-session
  workspace and the agent starts writing files. Installing a package outside the allowlist
  asks for approval in the UI; the auto-run loop builds and runs the app after each turn
  and sends build errors back to the agent.

## Troubleshooting

Run `doctor.bat`, or `services\vibe\.venv\Scripts\python.exe -m vibe doctor`. Each
heading below is the real doctor check name.

**`providers-configured` - "no provider has a key".** The app starts but no chat can
run. Set `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`) in a `.env` file at the
repository root, or add a provider in the app's **Settings** panel (stored in
`<workspace_dir>\providers.json`). A warning, not a blocker. The doctor proves a key is
*present*, not that it works.

**`chromium` - "no Playwright browser download found".** The agent cannot see the app
(no console logs, no screenshots); everything else works. Run
`services\vibe\.venv\Scripts\python.exe -m playwright install chromium`. A warning, not
a blocker.

**`port-backend` - "127.0.0.1:7321 is already in use".** Blocking. Free whatever holds
port 7321; `start.bat` runs the doctor before it starts, so this has to pass. The
doctor's remedy also names `set VIBE_PORT=<port>`, which a bare `python -m vibe serve`
honours.

**`pnpm` - "not found on PATH" or "did not report a version".** Blocking. Install it
with `npm install -g pnpm`, then reopen the terminal. If the npm registry is unreachable
the remedy adds "connect once and retry".

**`node` - "not found on PATH" or a version below 20.** Blocking. Install Node 20+ from
https://nodejs.org and reopen the terminal; upgrade if the reported version is older.

The doctor's other checks are `python` (blocking), `uv` (warning), `workspace` - the
workspace directory is writable (blocking) - `providers-file` (warning: an unreadable
`providers.json` is quarantined) and `port-frontend` (blocking: port 5173, the Vite dev
port).

## Where your data lives

Everything is under one workspace root, by default `C:\Users\<you>\vibe-workspaces`
(`~/vibe-workspaces`). Set `VIBE_WORKSPACE_DIR` to move it.

```
<workspace_dir>\
  sessions.db          chat sessions (SQLite)
  events.db            per-session event history (SQLite)
  providers.json       providers you added
  settings.json        saved settings (for example the system prompt)
  dev-servers.json     pidfile of dev servers the executor started
  <session-id>\        the generated project for one session
  logs\vibe.log        rotating log (2 MiB x 5; level from VIBE_LOG_LEVEL)
  .trash\<sid>-<ts>\   deleted sessions' workspaces (kept VIBE_TRASH_RETENTION_DAYS, default 14)
  backups\             output of vibe backup
```

Deleting a session moves its workspace to
`<workspace_dir>\.trash\<session-id>-<timestamp>` instead of erasing it. If a file in
the workspace is still open in another program, the delete answers with the error code
`workspace_busy` (HTTP 409) and leaves the session intact so you can close the program
and try again. `health` reports the resolved `workspace_dir`, `sessions_db` and
`events_db` paths.

The log rotates at 2 MiB and keeps five files; set `VIBE_LOG_LEVEL` to change the level
(default `INFO`) and `VIBE_LOG_FILE=off` to turn the file off (the console keeps
logging).

## Back up

```bat
services\vibe\.venv\Scripts\python.exe -m vibe backup
```

Copies `sessions.db`, `events.db` and `providers.json` into
`<workspace_dir>\backups\<YYYYMMDD-HHMMSS>\` with a `manifest.json`. It is safe while
the app is running: each database is copied through SQLite's own backup API. The newest
seven backups are kept; `--keep N` changes that. Generated projects are deliberately not
copied - copy `<workspace_dir>\<session-id>` yourself if you want them.

```bat
services\vibe\.venv\Scripts\python.exe -m vibe repair
```

checks both databases with `PRAGMA integrity_check`, re-runs migrations, and quarantines
an unreadable `providers.json` as `providers.json.corrupt-<timestamp>`. It never
deletes user data.

## Uninstall

1. Delete the workspace directory (`C:\Users\<you>\vibe-workspaces` by default) - this
   removes every session, generated project, log, trash entry and backup.
2. Delete the backend environment: `services\vibe\.venv`.
3. Optionally delete the repository clone, including `node_modules` and
   `apps\vibe\node_modules`.

## Known gaps

- **Authentication is loopback, or a shared secret.** Every route except `health` sits behind
  an authenticator, and state-changing requests must also carry a trusted `Origin`. A loopback
  bind trusts this machine only; binding beyond loopback now requires `VIBE_AUTH_TOKEN`, after
  which remote peers must send `Authorization: Bearer <token>`. There are still no per-user
  accounts (`Principal.id` is always `local`).
- **Local-only by design.** No account, no cloud service, no telemetry. The only remote
  calls are the LLM endpoint you configure and the package registries a generated app
  installs from.
- **Browser tools need Chromium.** Without it the agent cannot read console logs or take
  screenshots; those methods degrade to `None` rather than failing.
- **Provider keys live in two places.** Built-in providers (OpenAI, Anthropic, OpenCode Go)
  read their key from the environment or a dotenv file and are shown in Settings as
  configured or not; custom providers are added, edited and deleted in the Settings panel
  and stored in `<workspace_dir>\providers.json`.
- **The code editor loads Monaco from a CDN** (`@monaco-editor/react` with no local
  loader configured), so the code view needs network access the first time.
- **The system prompt has three layers.** Settings -> System prompt edits
  `<workspace_dir>\settings.json`; `VIBE_SYSTEM_PROMPT` overrides that file, and the
  panel disables its field while the environment is in charge. An empty value falls back
  to the built-in prompt. `VIBE_HISTORY_MESSAGES` (default 24) caps how much
  conversation is replayed to the model each turn.
- **Generated code runs with your own permissions** - the local-first trade-off. Installs
  outside the allowlist need approval, but the built app is code on your machine.

## Develop

- `test.bat` runs the backend tests, then the frontend tests. `doctor.bat` is the
  preflight.
- Backend, from `services\vibe`: `.venv\Scripts\python.exe -m pytest -q`; lint with
  `.venv\Scripts\python.exe -m ruff check .`
- Frontend, from `apps\vibe`: `pnpm test`, `pnpm run lint`, `pnpm run typecheck`,
  `pnpm run format:check`
- It is a pnpm workspace; the root `package.json` also exposes `pnpm test`,
  `pnpm build`, `pnpm lint`, `pnpm typecheck`, `pnpm test:backend` and
  `pnpm lint:backend`.
- Setup details, provider keys and the full walkthrough:
  [docs/guides/local-setup.md](docs/guides/local-setup.md).
