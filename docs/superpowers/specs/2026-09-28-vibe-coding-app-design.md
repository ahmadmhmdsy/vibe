# Vibe Coding App — Design Spec

Status: **Draft for user review** (2026-09-28). Created from the approved brainstorming design (Sections 1–8 plus the usage/cost addition).

## 1. Product

A local-first vibe-coding IDE. The user describes an app idea in chat; an agent builds it as a multi-file React (Vite + TypeScript) project, installs dependencies, builds, runs, and previews it — with an auto-run verify-fix loop that catches and fixes build/runtime errors. The user can chat with the agent, pick the model, manage multiple sessions, view the code (Monaco), and watch the live preview.

## 2. Decisions (user-confirmed)

| # | Decision | Options considered | Chosen |
|---|---|---|---|
| 1 | Execution environment | Server-side sandbox / browser-side (WebContainers) / hybrid | **Server-side sandbox** |
| 2 | Deployment target | Local-first now, scale later | **Local-first** |
| 3 | MVP scope | Core loop first / everything / narrowest | **Core loop first** |
| 4 | Agent tools | Full suite / minimal / full + browser interaction | **Full suite** |
| 5 | LLM providers | Provider-agnostic (OpenAI + Anthropic) + custom OpenAI/Anthropic-compatible + OpenCode Go | **Chosen** |
| 6 | Agent architecture | LangGraph + local subprocess / Docker-per-day-one / imperative loop | **LangGraph + local subprocess** |
| 7 | Reusability | deepseek-harness-inspired seams (capability seams, registries, event log, composition) | **Approved** |
| 8 | Usage & cost tracking | Added (tokens in/out/cached/cache_hit/total + steps + cost USD) | **Approved** |
| 9 | Operational metrics | Later (build/install duration, files written, screenshots) | **Added to later list** |

## 3. Architecture

Inspired by deepseek-harness's "everything-is-a-plugin" philosophy — capability seams, registries, an append-only event log, and composition at the edges — implemented with plain Python interfaces + FastAPI dependency injection + a small registry (no plugin-framework lock-in).

### 3.1 Seam map

Every swappable part has three roles: **Definition** (interface), **Provider** (implementation), **Consumer** (the part that uses it).

| Seam | Definition | Providers | Consumer |
|---|---|---|---|
| **LLM** | `LlmProvider` — chat, stream, tool-calls | OpenAI, Anthropic, OpenCode Go, custom OpenAI/Anthropic-compatible | Agent runtime |
| **Agent runtime** | `AgentRuntime` — `run(input) -> event stream` | LangGraph adapter (today), any future framework | Chat API, auto-run |
| **Executor** | `Executor` — install, build, run, stop, logs, screenshot | Local subprocess (today), Docker (later) | Agent tools |
| **Tools** | `ToolRegistry` — schema + handler registrations | file/build/run/screenshot tools | Agent runtime |
| **Sessions** | `SessionStore` — events, metadata, resume | SQLite (today), Postgres (later) | API, UI |
| **Events** | `EventBus` — append + subscribe | SQLite-backed log + SSE (today) | Chat UI, auto-run, future CLI |

### 3.2 Module diagram

```
┌────────────────────────── React frontend (apps/vibe) ──────────────────────────┐
│  chat/  sessions/  preview/  code/ (Monaco)  settings/  — feature modules      │
│  Composed at the app root; each module owns its routes, state, and components   │
└────────────────────────────────┬─────────────────────────────────────────────────┘
                                 │ HTTP + SSE (typed events)
┌────────────────────────────────┴─────────────────────────────────────────────────┐
│                        FastAPI backend (services/vibe)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ AgentRuntime │  │  ToolRegistry│  │  LlmProvider │  │     Executor       │  │
│  │ (LangGraph)  │  │  (10 tools)  │  │  (4+ providers)│  │ (local subprocess) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘  │
│  ┌──────┴─────────────────┴─────────────────┴────────────────────┴──────────┐  │
│  │              EventLog (append-only, per session) + EventBus (SSE)         │  │
│  └──────────────────────────────────┬─────────────────────────────────────────┘  │
│  ┌──────────────────────────────────┴─────────────────────────────────────────┐  │
│  │        SessionStore (SQLite)  ·  Workspace FS  ·  Config/credentials       │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Data flow for one turn

User message → appended to the session EventLog → `AgentRuntime.run()` streams events (text chunks, tool calls) → tool handlers execute against the Executor/Workspace → results appended to the log → SSE broadcasts to the chat UI → auto-run policy watches for "build needed / preview stale" events and triggers the verify-fix loop.

### 3.4 Two rules that keep it reusable

- **Model-visible means logged** — anything the agent sees is reconstructable from the EventLog; resume, replay, and testing all derive from one source.
- **Every module exposes a narrow interface and nothing reaches across seams** — the chat UI never imports the executor; the agent never imports FastAPI.

## 4. Agent runtime & tools

### 4.1 AgentRuntime seam

```python
class AgentRuntime(Protocol):
    async def run(self, input: AgentInput, ctx: AgentContext) -> AsyncIterator[AgentEvent]: ...

@dataclass
class AgentInput:
    session_id: str
    messages: list[Message]        # new user messages
    attachments: list[Attachment]  # images (post-MVP)
    model: ModelRef                # provider/model chosen in the UI

@dataclass
class AgentEvent:                   # streamed via SSE, appended to EventLog
    kind: Literal["text_chunk", "tool_call", "tool_result", "error", "turn_complete"]
    ...
```

The **LangGraph adapter** is one implementation: a graph with a `call_model` node and an `execute_tools` node that loop until the model stops calling tools. Every event it yields is appended to the session EventLog and broadcast.

**The swap:** replacing LangGraph with another framework = writing one new `AgentRuntime` implementation. The FastAPI routes, EventLog, ToolRegistry, Executor, and auto-run driver never change — they consume the interface.

### 4.2 Tool registry

Tools are registered as `(name, JSON schema, handler)` triples. The handler gets a `ToolContext` (workspace path, executor, event bus) and returns a result appended to the log.

| Tool | Purpose | Guardrails |
|---|---|---|
| `write_file` / `edit_file` / `read_file` | create, edit, read project files | workspace-only paths, size caps |
| `list_files` | project tree | — |
| `install_deps` | add npm packages | timeout, supply-chain policy (§9) |
| `build` | `vite build` | timeout, output truncation |
| `run_dev_server` / `stop_dev_server` | start/stop the preview | port allocation, process cleanup |
| `read_console_logs` | browser console output | tail, truncation |
| `screenshot` | capture the running app | viewport size cap |

Adding a tool = one registration; removing one = deleting its registration. The loop discovers tools from the registry at runtime.

### 4.3 Auto-run verify-fix loop

Auto-run is a **policy that composes runtime calls — not a branch inside the loop.** After each turn, if source files changed, the `AutoRunPolicy` fires:

```
build → run_dev_server → wait for ready → read_console_logs + screenshot
  ├─ clean → done (preview shows the result)
  └─ errors → AgentRuntime.run() again with a synthetic fix turn:
       "The app failed: <console errors + build output>. Fix it."
       → repeat, up to N iterations (default 3), then stop and report
```

A fix turn is just another `AgentRuntime.run()` call — same tools, same event stream, same log. The agent can also run the app itself mid-turn via the `run_dev_server` tool; auto-run is the safety net when it forgets. The policy is behind an `AutoRunPolicy` interface (swappable/stricter/looser/disable).

**Caps:** max fix iterations per turn, per-session token budget, hard timeout on the whole verify-fix cycle.

## 5. Providers

### 5.1 Provider interface

```python
class LlmProvider(Protocol):
    id: str
    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatEvent]: ...
    # ChatRequest: messages, tools, model, temperature, attachments
```

Three protocol flavors:

| Flavor | Endpoint style | Used by |
|---|---|---|
| `openai-chat` | `/v1/chat/completions` | OpenAI, most OpenCode Go models, custom OpenAI-compatible |
| `openai-responses` | `/v1/responses` | OpenCode Go's Grok / GPT-Luna / Muse models |
| `anthropic-messages` | `/v1/messages` | Anthropic, OpenCode Go's MiniMax / Qwen models |

### 5.2 Providers are data, not code

A provider is a config row stored server-side — adding one is a settings-UI action, zero code:

```json
{
  "id": "opencode-go",
  "name": "OpenCode Go",
  "baseUrl": "https://opencode.ai/zen/go/v1",
  "apiKey": "sk-…",
  "models": [
    { "id": "opencode-go/kimi-k3",   "protocol": "openai-chat" },
    { "id": "opencode-go/grok-4.7",   "protocol": "openai-responses" },
    { "id": "opencode-go/minimax-m3", "protocol": "anthropic-messages" }
  ]
}
```

**OpenCode Go** ships as a built-in provider definition (fixed base URL, key from the OpenCode Zen console, per-model protocol routing, model discovery via `GET /v1/models`). **Custom providers** are user-defined rows: name, protocol, base URL, API key, and either a static model list or a discovery URL. The LangGraph adapter builds the matching LangChain chat model from the row (`ChatOpenAI` for the two OpenAI flavors, `ChatAnthropic` for the Anthropic flavor).

### 5.3 What the frontend sees

The model picker calls a catalog endpoint returning only `id`, display name, and capabilities (tool support, vision) — never keys or base URLs. Keys never leave the server and never enter the React bundle.

## 6. Executor & preview

### 6.1 Executor interface

```python
class Executor(Protocol):
    async def install(self, packages: list[str]) -> ToolResult: ...
    async def build(self) -> ToolResult: ...
    async def start_dev_server(self) -> DevServerHandle: ...   # → local port + URL
    async def stop_dev_server(self) -> None: ...
    async def read_console_logs(self, tail: int) -> str: ...
    async def screenshot(self) -> bytes: ...
```

The **LocalSubprocessExecutor** implements it with `asyncio` subprocesses (`pnpm install`, `vite build`, `vite dev`) and a Playwright-driven headless Chromium for console capture and screenshots. Every method has a timeout and output truncation. The **DockerExecutor** (later) implements the same interface — the agent tools and auto-run never know the difference.

### 6.2 Workspace and template

Each session gets a workspace directory on local disk:

```
~/vibe-workspaces/<session-id>/
├── package.json · vite.config.ts · index.html
└── src/ (main.tsx, App.tsx, …)
```

On session creation the backend scaffolds the workspace from a **built-in Vite + React + TS template** — the agent edits app code within a working project. `install_deps` runs the package manager inside the workspace; the dev server runs there too.

### 6.3 Preview flow

```
agent calls run_dev_server
  → Executor starts `pnpm dev --port <port>` in the workspace
  → waits for ready (poll the port / parse stdout)
  → returns the URL to the frontend
frontend: <iframe src="http://127.0.0.1:<port>/" />
```

For MVP the iframe loads the dev server URL **directly** — cross-origin iframes are fine for display, and Vite's HMR websocket works without a proxy. A same-origin FastAPI proxy (`/preview/{session_id}/*`) is a later option for custom domains and port hiding, not a v1 need.

### 6.4 Console + screenshot capture

The backend keeps a headless Chromium pointed at the preview URL:

- **Console:** Playwright listens to `console` and `pageerror` events, buffers them; `read_console_logs` returns the tail. This is how the auto-run loop *sees* runtime errors.
- **Screenshot:** `screenshot` captures the viewport → bytes → shown inline in the chat. This is how the agent *sees* visual bugs.

### 6.5 Lifecycle

The dev server starts on the first `run_dev_server` (or auto-run), stays alive for the session, and is stopped on session delete or after an idle timeout. Ports are allocated from a fixed local range. Process cleanup is guaranteed on backend shutdown.

## 7. Sessions & events

### 7.1 EventLog

Every durable fact about a session is an appended event:

```
user/message · assistant/message · tool/call · tool/result
build/status · preview/updated · session/meta · usage
```

The model's visible history is *derived* from the log (LangGraph checkpoint + log replay); the chat UI is *rendered* from the log. Live-only events (stream chunks) are never persisted — they exist for the UI in the moment, then the durable `assistant/message` settles them. Invariant: replay the log and you can reconstruct exactly what the agent saw.

### 7.2 SessionStore (SQLite)

```
sessions(id, title, model_ref, created_at, updated_at)
events(session_id, seq, type, payload)   -- append-only, ordered
```

Multi-session management is CRUD over the sessions table plus its event stream:

- **List** — sidebar shows title, last activity, model badge.
- **Create** — new session → scaffold workspace from template → fresh log.
- **Rename / Delete** — delete stops the dev server and removes the workspace.
- **Resume** — load the log → restore LangGraph checkpoint → continue. The frontend replays the log to rebuild chat history, then attaches to the live stream.

### 7.3 SSE streaming

The frontend subscribes to `/sessions/{id}/events` (Server-Sent Events). Every appended event is broadcast; stream chunks flow here too. On reconnect, the client sends its last-seen `seq` and the server replays from there — no missed messages, no duplicate rendering.

### 7.4 Event flow

```
user sends message
  → appended to EventLog as user/message
  → AgentRuntime.run() streams assistant/tool events
  → each durable event appended + broadcast via SSE
  → auto-run policy reacts (build/preview events)
  → frontend re-renders chat from the log + live stream
```

One log, one stream, every consumer (chat UI today, a future CLI or test harness tomorrow) reads the same source.

## 8. Frontend

### 8.1 Feature modules, composed at the root

```
apps/vibe/src/
├── features/
│   ├── chat/        # message list, composer, model picker, streaming
│   ├── sessions/    # sidebar: list, create, rename, delete
│   ├── preview/     # iframe, run/stop, console view
│   ├── code/        # Monaco + file tree (read-only for MVP)
│   └── settings/    # provider management, API keys
├── app/             # composition root: layout, wiring
├── lib/             # typed API client, SSE client (reconnect + seq replay)
└── components/      # shared UI primitives
```

Each feature module owns its state (a zustand store, matching this repo's FlowForge convention), its components, and its API calls. The app root composes them — removing a feature means removing its module from the composition. The chat module never imports the preview module; both talk to the backend through `lib/`.

### 8.2 Panels

- **Sessions sidebar (left):** list with title, last activity, model badge; create/rename/delete; click to switch (switches the active SSE subscription + workspace).
- **Chat (center):** full history rendered from the EventLog — user/assistant messages, tool calls as collapsible cards (build status, install output, screenshots inline). Model picker populated from the catalog endpoint. Text input with send; image attach is post-MVP. Streaming chunks append to the live assistant message via SSE.
- **Preview (right, tabbed):** the running app in an iframe, plus a toolbar — run/stop, open console, screenshot. A console tab shows captured browser logs (the same feed the auto-run loop reads).
- **Code (right, tabbed):** Monaco with a file tree, **read-only for MVP** — the agent's output is visible and inspectable. Hand-editing with agent sync is a noted follow-up (Cursor-style), not v1.
- **Settings:** provider management — built-in providers show masked key status; custom providers can be added/edited/deleted (name, protocol, base URL, key, model list). Keys are typed here and stored server-side only.

### 8.3 Layout

Three-pane IDE: sessions | chat | preview+code. Resizable panes, responsive collapse on narrow screens. The layout is a composition of the feature modules — swapping the right pane to a different arrangement is a layout change, not a feature change.

## 9. Security & limits

### 9.1 Local-first security model

**Generated code runs with the user's own permissions.** The agent can read/write its workspace, install npm packages, and run processes — exactly what the user could do themselves by running `npm install` in a terminal. For a local dev tool that's acceptable (same trust level as the user's own `node_modules`), but it must be documented, not hidden.

### 9.2 Mitigations (all behind the seams)

- **Workspace confinement:** the agent's file tools are restricted to the session workspace directory — path allowlists reject anything outside.
- **Command allowlist:** the executor runs only known commands (`pnpm install`, `vite build`, `vite dev`) with fixed flags — no arbitrary shell.
- **Timeouts + truncation:** every tool has a timeout and output cap; the dev server has an idle timeout.
- **Supply-chain policy:** npm installs are the real risk. MVP policy: log every installed package, and require user approval for dependencies outside a starter allowlist (React, Vite, common UI libs). The approval prompt is a chat event — the user sees "agent wants to install `date-fns`" and approves/denies.
- **Secrets:** LLM API keys live server-side, encrypted at rest, never in the React bundle. The frontend sees only provider names and masked key status.

### 9.3 Resource limits

- Per-session token budget (configurable) — stops runaway verify-fix loops.
- Max fix iterations per turn (default 3) + a hard timeout on the whole verify-fix cycle.
- Disk quota per workspace; dev server killed on session delete or idle timeout.

### 9.4 What changes when we scale

The Docker executor (behind the same `Executor` interface) adds OS isolation, network egress policy, and CPU/memory limits. The supply-chain approval policy, token budgets, and workspace confinement stay exactly the same — they're consumers of the seams, not properties of the local executor.

## 10. Usage & cost tracking

### 10.1 UsageRecord (per LLM call / step)

The provider seam captures usage from the streaming response and normalizes it (OpenAI, Anthropic, and OpenCode Go each report differently). Each record is appended to the EventLog as a `usage` event, broadcast via SSE, and aggregated by the SessionStore.

```json
{
  "provider": "openai", "model": "gpt-4o",
  "input_tokens": 1200, "output_tokens": 350,
  "cached_tokens": 800, "cache_write_tokens": 0,
  "cache_hit": true, "cache_hit_rate": 0.4,
  "total_tokens": 2350, "cost_usd": 0.012
}
```

- **Granularity:** the *step* (one model request + its tool calls) is the atomic unit; usage aggregates **per turn** (shown next to each assistant message) and **per session** (stats area). One record, three views.
- **`cache_write` tokens:** Anthropic charges for *writing* to the prompt cache, not just reading — tracked separately so cache costs are visible.
- **`cache_hit_rate`:** `cached / (input + cached)` — more useful than a boolean for judging cache effectiveness.
- **Cost in USD:** derived from a configurable price table (prices change, so it's data, not code).
- **Per-model attribution:** if the user switches models mid-session, usage and cost break down by model.
- **Fix-iteration count:** each auto-run verify-fix cycle burns tokens; the user sees "3 fix iterations, 12k tokens, $0.04".
- **Timing:** usage is only known when the LLM call *completes* (the final streaming chunk carries it) — the badge populates when the step settles, not when the message sends.

### 10.2 UI placement

- **Per assistant message badge:** tokens (in/out/cached) + cost + steps + tool calls.
- **Session stats:** total in/out/cached/cost/steps/fix-iterations, with a per-model breakdown.
- Usage records are durable events — the same log that drives chat history drives the stats.

## 11. Scope & milestones

### 11.1 In vs. out

**In (the product):** everything approved in Sections 3–10 — the agent runtime seam, tool registry, provider seam (OpenAI, Anthropic, OpenCode Go, custom), executor + preview pipeline, event log + sessions, auto-run verify-fix, usage/cost tracking, and the five frontend feature modules.

**Out (YAGNI, deferred):** audio input, auth, Docker executor, Postgres, deployment, arbitrary shell access. These arrive behind the seams when they're needed — not before.

### 11.2 Milestones

| Milestone | Goal | Delivers |
|---|---|---|
| **M1 — Core loop** | Prove the loop end-to-end | Single-session chat → agent writes a Vite+React+TS app → installs deps → builds → runs → preview → auto-run verify-fix. Provider seam live. |
| **M2 — Sessions & models** | The UI layer | Multi-session management (list/create/rename/delete/resume), model picker, provider settings UI. Cheap because the seams already exist. |
| **M3 — Polish** | Make it feel like a product | Image input (reference designs, screenshot feedback), Monaco hand-editing, supply-chain approval UI, token budgets, a11y audit, full test coverage. |
| **M4 — Scale** | The growth path | Docker executor, Postgres, auth, deployment — all behind the same interfaces, no agent changes. |

**M1 is the riskiest and most important** — if the verify-fix loop doesn't produce working apps, nothing else matters, so it gets proven first with a single session. Everything after M2 is UI and polish layered on a proven core.

### 11.3 Validation

Frontend: vitest + typecheck + lint (repo conventions). Backend: pytest + typecheck. E2E smoke: drive a real session — prompt, generate, build, run, preview, auto-fix — and verify the preview renders. Docs: PLAN/HANDOFF/TASKS/MEMORY/ENVIRONMENT updated per the repo's doc map.

## 12. Open items

- **App name:** working name "vibe" (apps/vibe + services/vibe) — to be confirmed.
- **Image input timing:** M3 (post-MVP).
- **Monaco hand-editing:** M3 (post-MVP).
- **Operational metrics (later, not v1):** build/install duration, files written, screenshots taken — as a session activity view. Cheap to add once usage logging exists, but not core.
