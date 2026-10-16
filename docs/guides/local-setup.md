# Local setup walkthrough

[README.md](../../README.md) is the quick path: requirements, install, run, troubleshooting.
This guide is the longer one - what you are installing, how to wire up a model provider, what a
first app looks like end to end, what the app does when the network is gone, and the deeper
version of the troubleshooting list.

Everything here is local. There is no account, no payment, no cloud service. The API listens on
loopback only, and the only outbound traffic is the LLM provider you configure plus the package
downloads a generated app needs.

## 1. What you are installing

Two processes and one directory:

| piece | what it is | where it lives |
|---|---|---|
| backend | FastAPI + the LangGraph agent; owns sessions, events, providers, the executor and the preview | `services/vibe` (Python 3.13 venv) |
| frontend | the React SPA, built by Vite into static files | `apps/vibe` -> `apps/vibe/dist` |
| workspace | your chats, the generated projects, logs and backups | `C:\Users\<you>\vibe-workspaces` by default |

In the normal one-command run the backend serves the built SPA **and** the API on a single
loopback port, so there is nothing extra to start. `start.bat dev` keeps the two-process
development workflow (Vite with hot reload on 5173, the API on its own port).

## 2. Prerequisites

| requirement | version in this repo | doctor check | blocking? |
|---|---|---|---|
| Python | 3.13.1 (needs >= 3.13) | `python` | yes |
| Node | v24.18.0 (needs >= 20) | `node` | yes |
| pnpm | 12.3.4 (pinned by `packageManager`) | `pnpm` | yes |
| uv | 0.11.x | `uv` | no - only needed to build the venv |
| Playwright chromium | any current build | `chromium` | no - without it the agent cannot see the app |
| free ports | 7321 (API), 5173 (dev UI) | `port-backend`, `port-frontend` | yes |

Check the machine at any time with:

```bat
doctor.bat
```

One `PASS`/`FAIL` line per check, and under each failure the exact remedy. The last line is
either `all checks passed - the app can run on this machine` or a count of blocking problems.

## 3. Install (once; needs a network connection)

From the repository root:

```bat
cd services\vibe
uv sync --extra dev
.venv\Scripts\python.exe -m playwright install chromium
cd ..\..
pnpm install
pnpm run build
```

- `uv sync --extra dev` creates `services\vibe\.venv` and installs the pinned backend
  dependencies, including pytest and ruff.
- the Playwright download is what lets the agent read console logs and take screenshots.
- `pnpm install` installs the frontend toolchain into `node_modules`.
- `pnpm run build` compiles the SPA into `apps\vibe\dist`. The one-command run serves that
  build; without it `start.bat` stops with a `RuntimeError` telling you to run the build.

The backend itself is always run through the venv interpreter,
`services\vibe\.venv\Scripts\python.exe`, never a bare `python`.

## 4. Configure a model provider

The app ships no key. Until one is configured the app starts, the UI works, and no chat can
run - the doctor says so as the warning `providers-configured`.

**Option A - a dotenv file at the repository root.** Create `.env` (it is gitignored) and put
the key for a supported provider there:

```
OPENAI_API_KEY=<your OpenAI key>
ANTHROPIC_API_KEY=<your Anthropic key>
OPENCODE_API_KEY=<your OpenCode Go key>
```

Fill in only the provider you use. The loader reads a dotenv file from the current directory and
up to three parent directories, and never overwrites a variable that is already set in the
environment. `.env.example` lists the same names with empty values.

**Option B - the Settings panel.** Add a provider by name, base URL, key and model. This works
for any OpenAI-compatible endpoint, which is how a local model server is used. The entry is
written to `<workspace_dir>\providers.json`. An unreadable `providers.json` is quarantined as
`providers.json.corrupt-<timestamp>` and reported as "no custom providers" rather than crashing
a request.

**Option C - environment variables**, for a built-in provider, wherever you already keep
secrets.

Then confirm:

```bat
doctor.bat
```

`providers-configured` should name at least one provider. The doctor proves a key is
**present, not that it works** - the first chat is the real test. Keys stay on the backend: the
API returns masked values and never sends a key to the browser bundle. Never commit a key.

### The system prompt (optional)

**Settings -> System prompt** edits the instructions the agent starts from. Three layers,
highest first:

```
VIBE_SYSTEM_PROMPT (environment)  >  <workspace_dir>\settings.json  >  built-in default
```

The panel shows which layer is in charge and disables its field when the environment wins,
because the environment is the operator override. Saving writes `<workspace_dir>\settings.json`
and applies on the next turn - no restart. Clearing the box removes the saved override and falls
back to the built-in prompt; a whitespace-only value counts as unset, so an empty
`VIBE_SYSTEM_PROMPT` never strips the agent of all framing.

## 5. Your first app

1. Run `start.bat` (section 6). The doctor runs first; once it passes, the browser opens on the
   printed URL.
2. Pick a model in the picker and describe the app you want in the chat box.
3. Send. The first turn creates `<workspace_dir>\<session-id>` and the agent starts writing
   files: `package.json`, `index.html`, `src/main.tsx` and the rest of a Vite + React +
   TypeScript project.
4. Installing a dependency outside the allowlist raises an **approval card** in the chat. Nothing
   is installed until you approve it.
5. After each turn the auto-run loop installs, builds and runs the app, and feeds build errors
   back to the agent, which fixes them and tries again (up to `VIBE_MAX_FIX_ITERATIONS`
   attempts, default 3). The preview panel then serves the app.
6. **Stop** interrupts an in-flight run. If the run already finished, the request reports
   `aborted=false` rather than pretending it stopped something.
7. Closing and reopening the app keeps the transcript: sessions are in `sessions.db` and the
   event history in `events.db`, both SQLite, both resumable.
8. The Code panel shows the generated project as a file tree with a Monaco editor; edits you make
   there are used by the next build.

## 6. Running and stopping

```bat
start.bat            :: doctor, first free port from 7321, backend, wait for /health, open browser
start.bat dev        :: Vite with hot reload on 5173 plus the API in this window
stop.bat             :: ask the server to shut down, then verify the port is actually free
stop.bat 7400        :: the same for a different port
doctor.bat           :: prerequisite check only
```

Ctrl+C in the `start.bat` window stops everything. All three scripts are thin wrappers over
`python -m vibe <serve|doctor|backup|repair>`, but the wrapper does real work the bare command does
not: it runs the doctor, picks the first free port from 7321, sets `VIBE_HOST`, `VIBE_MODE` and the
browser URL, and opens the browser only once `/health` answers. If you run the module directly,
set the mode yourself:

```bat
set VIBE_MODE=prod
set VIBE_HOST=127.0.0.1
set VIBE_PORT=7321
services\vibe\.venv\Scripts\python.exe -m vibe serve
```

Without `VIBE_MODE=prod` the server is API-only: `GET /` answers `404` with a JSON body instead of
the app. In `prod` mode the SPA and the API share that one origin, which the server trusts because it
serves it; `VIBE_CORS_ORIGINS` exists for the dev split (Vite on 5173, the API elsewhere).

The log goes to the console and to `<workspace_dir>\logs\vibe.log`, rotating at 2 MiB and
keeping five files. `VIBE_LOG_LEVEL` sets the level (default `INFO`); `VIBE_LOG_FILE=off`
keeps the console output and stops the file.

## 7. Offline and semi-offline notes

- **Model calls need the network.** That is the one thing that cannot work offline; the rest of
  the app does not talk to anything.
- **A generated app's first install needs the network**, because it downloads packages from the
  npm registry. After that the app is on disk.
- **The doctor and the UI degrade honestly.** A reachability probe is cached - a success for
  300 s, a failure for 30 s - so an offline machine is told it is offline instead of hanging. The
  `pnpm` check's remedy adds "connect once and retry" when the registry is unreachable. An
  install fails fast with "no network access to the npm registry - connect once to install
  dependencies, then retry (nothing was downloaded)".
- **The code editor loads Monaco from a CDN** (`@monaco-editor/react` with no local loader
  configured), so the code view may not render offline. The rest of the SPA is served from the
  local build.
- **Install once online, then you can stay offline** for everything except new model turns and
  new package installs.

## 8. Where your data lives, and how to back it up

```
<workspace_dir>\
  sessions.db          chat sessions (SQLite)
  events.db            per-session event history (SQLite)
  providers.json       providers you added
  settings.json        saved settings (for example the system prompt)
  dev-servers.json     pidfile of dev servers the executor started
  <session-id>\        the generated project for one session
  logs\vibe.log        rotating log
  .trash\<sid>-<ts>\   deleted sessions' workspaces (kept 14 days by default)
  backups\             output of vibe backup
```

Deleting a session moves its workspace to the trash directory (`.trash`) instead of erasing
it. If a file is still open in another program the delete answers `workspace_busy` (HTTP 409)
and leaves the session intact, so you can close the program and try again - the workspace is
never half-moved.

```bat
services\vibe\.venv\Scripts\python.exe -m vibe backup
services\vibe\.venv\Scripts\python.exe -m vibe repair
```

`vibe backup` copies `sessions.db`, `events.db` and `providers.json` through SQLite's own
backup API, so it is safe while the app is running, and keeps the newest seven (`--keep N`
changes that). Generated projects are deliberately not copied. `vibe repair` checks both
databases with `PRAGMA integrity_check`, re-runs migrations, quarantines an unreadable
`providers.json`, and never deletes user data.

## 9. Running the checks yourself

```bat
:: backend, from services\vibe
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .

:: frontend, from apps\vibe
pnpm test              :: vitest, a single pass
pnpm run test:watch    :: vitest in watch mode
pnpm run typecheck
pnpm run lint
pnpm run format:check
pnpm run build
```

`test.bat` runs the backend suite and then the frontend suite and pauses at the end. The root
`package.json` exposes `pnpm test`, `pnpm build`, `pnpm lint`, `pnpm typecheck` and
`pnpm format:check`, plus `pnpm test:backend` and `pnpm lint:backend` for the Python side.
`pnpm test` is `vitest run`, a single pass that exits - do not write `pnpm test -- --run`.
Two scripts wrap a full verification pass over the repository. Both declare `#Requires -Version 7.0`
and must be run with **PowerShell 7** (`pwsh`), not Windows PowerShell 5.1. On 5.1 they stop at the
first line with a message naming the version they need - which is the point: 5.1 parses a top-level
JSON array and passes a multi-line argument to a native command differently, and failing halfway
through a check run is worse than not starting it.

```bat
:: from the repository root - the whole loop end to end on an isolated temp workspace
pwsh -File scripts\acceptance-local.ps1
pwsh -File scripts\acceptance-local.ps1 -FullE2E

:: every gate a maintainer runs before handing a build to someone
pwsh -File scripts\release-check.ps1
```

The acceptance run prints one label per criterion and appends everything to
`artifacts/acceptance-local.txt`; the release check stops at the first red step and writes
`artifacts/release-check.txt`. Neither touches your real workspace: every server they start points
`VIBE_WORKSPACE_DIR` at a temporary directory.

## 10. Troubleshooting in depth

All ten checks, in the order the doctor runs them:

| Check | Blocking | Fails when | Remedy |
|---|---|---|---|
| `python` | yes | Python is older than 3.13 | install Python 3.13+ and recreate the venv |
| `node` | yes | node is missing, silent, or older than 20 | install or upgrade Node 20+ from nodejs.org, reopen the terminal |
| `pnpm` | yes | pnpm is missing or silent | `npm install -g pnpm` |
| `uv` | no | uv is not on PATH | install it from docs.astral.sh/uv if you need to rebuild the venv |
| `chromium` | no | no Playwright browser download was found | run the printed `playwright install chromium` command |
| `workspace` | yes | the workspace directory is not writable | set `VIBE_WORKSPACE_DIR` to a writable path |
| `providers-file` | no | `providers.json` exists but cannot be read | fix or delete it; the app quarantines it and starts |
| `providers-configured` | no | no provider has a key and no custom provider exists | set a key or add a provider in Settings |
| `port-backend` | yes | the backend port is in use | stop what holds it, or set `VIBE_PORT` |
| `port-frontend` | yes | the Vite dev port (5173) is in use | stop what holds it, or change `server.port` in `apps/vibe/vite.config.ts` |

A real all-green run from this machine, with the username replaced:

```
PASS  python                3.13.1
PASS  node                  24.18.0
PASS  pnpm                  12.3.4
PASS  uv                    C:\Users\<you>\AppData\Local\hermes\bin\uv.EXE
PASS  chromium              10 browser build(s), newest chromium_headless_shell-1243
PASS  workspace             C:\Users\<you>\vibe-workspaces
PASS  providers-file        1 custom provider(s) in providers.json
PASS  providers-configured  opencode-go, 1 custom
PASS  port-backend          127.0.0.1:7321 is free
PASS  port-frontend         127.0.0.1:5173 is free

all checks passed - the app can run on this machine
```

A blocking failure looks like this:

```
FAIL  port-backend          127.0.0.1:7321 is already in use
                            -> stop what is using 127.0.0.1:7321, or start on another: set VIBE_PORT=<port>

1 blocking problem(s): port-backend
cannot start until the blocking problems above are fixed
```

The five a first run is most likely to hit:

**No provider key (`providers-configured`)** - the app opens and sessions work, but a chat
turn cannot run. Put a key in `.env`, or add a custom endpoint in Settings. This is a warning,
so `start.bat` still starts.

**No Chromium (`chromium`)** - the agent loses the browser tools; it still writes code, but it
cannot inspect console errors or take a screenshot of its own work. Run
`services\vibe\.venv\Scripts\python.exe -m playwright install chromium`. Warning only.

**Backend port busy (`port-backend`)** - blocking. Free whatever holds `127.0.0.1:7321`.
`start.bat` runs the doctor before it starts, so this must pass for the one-click path; the
doctor's remedy also offers `set VIBE_PORT=<port>`, which a bare `python -m vibe serve`
honours.

**pnpm missing (`pnpm`)** - blocking. `npm install -g pnpm`, then reopen the terminal. When
the npm registry is unreachable the remedy says so; connect once and retry. The repo pins pnpm
12.3.4 in `package.json`.

**Node missing or too old (`node`)** - blocking. Install Node 20+ from https://nodejs.org, or
upgrade, and reopen the terminal. The repo runs on v24.18.0.

Two more that are easy to misread:

- **`providers-file`** failing does not mean a key is wrong - it means the JSON is unreadable.
  The app quarantines the file to `providers.json.corrupt-<timestamp>` and starts without your
  custom providers; fix or delete the original.
- **`workspace`** failing usually means a permissions or path problem. The doctor creates the
  directory and writes a probe file; if that fails, point `VIBE_WORKSPACE_DIR` at a directory
  you can write to.

## 11. Environment variables

Read once at startup. A dotenv file in the current directory or up to three parents is loaded
first, and never overwrites a variable that is already set.

| Variable | Default | What it does |
|---|---|---|
| `VIBE_WORKSPACE_DIR` | `~/vibe-workspaces` | workspace root; resolved to an absolute path |
| `VIBE_HOST` | `127.0.0.1` | bind address; a non-loopback value also requires `VIBE_AUTH_TOKEN` |
| `VIBE_PORT` | `7321` | backend port |
| `VIBE_MODE` | `dev` | `dev` = API only, Vite owns the UI; `prod` = serve the built SPA from the API. start.bat sets `prod`, or `dev` with `start.bat dev` |
| `VIBE_STATIC_DIR` | `apps/vibe/dist` | built SPA directory used in prod mode |
| `VIBE_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | origins allowed to send state-changing requests |
| `VIBE_AUTH_MODE` | `loopback` | authenticator; `loopback`, or `token` (selected automatically when `VIBE_AUTH_TOKEN` is set) |
| `VIBE_AUTH_TOKEN` | unset | shared secret; set it to bind beyond loopback — remote peers must send `Authorization: Bearer <token>` |
| `VIBE_MAX_FIX_ITERATIONS` | `3` | auto-run fix attempts per turn |
| `VIBE_HISTORY_MESSAGES` | `24` | prior messages replayed to the model |
| `VIBE_SYSTEM_PROMPT` | empty | replaces the built-in system prompt (wins over settings.json) |
| `VIBE_SESSION_TOKEN_BUDGET` | unset | optional per-session token budget; empty means unlimited |
| `VIBE_TRASH_RETENTION_DAYS` | `14` | days a deleted workspace stays under the trash directory; 0 keeps it forever |
| `VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN` | `30` | idle minutes before a generated app's dev server is stopped |
| `VIBE_BROWSER_HEADLESS` | `1` | `0` opens a visible browser for the agent |
| `VIBE_BROWSER_TIMEOUT_MS` | `10000` | browser operation timeout in milliseconds |
| `VIBE_LOG_LEVEL` | `INFO` | console and file log level |
| `VIBE_LOG_FILE` | `<workspace_dir>/logs/vibe.log` | log file path; `off` disables the file |
| `OPENAI_API_KEY` | unset | OpenAI credential |
| `ANTHROPIC_API_KEY` | unset | Anthropic credential |
| `OPENCODE_API_KEY` | unset | OpenCode Go credential |

## 12. Uninstall or reset

The app keeps no state outside two directories. To remove it:

1. stop it (`stop.bat` or Ctrl+C);
2. delete the workspace root (`C:\Users\<you>\vibe-workspaces` by default) - this removes
   every chat, generated project, log, trash entry and backup;
3. delete `services\vibe\.venv`, `node_modules` and `apps\vibe\dist`.

Step 2 is irreversible; run `vibe backup` first if you want the databases. Nothing is written
into the registry, no service is installed, and no account exists anywhere to cancel.
