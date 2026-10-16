# 02 — Backend findings

Scope: `services/vibe/src/vibe/` (all modules). Findings are proven by
`probes/backend_probe.py` (raw output: `evidence/backend-probe.txt`) or by
`evidence/baseline-*`. Reproduction commands assume cwd `services/vibe` with
`.venv\Scripts\python.exe`.

Severity legend is in [README.md](./README.md). "Deliberate?" records whether
the repository documents the behaviour as a conscious choice.

---

## What is genuinely strong

These are not consolation prizes; they are the reason the defects below are
worth fixing rather than rewriting around.

- **A real composition root.** `vibe/container.py` builds one frozen
  `Container`; routes declare `deps: App` and never touch `app.state`.
  Unknown overrides raise instead of being silently ignored. Swapping a seam
  swaps the whole derived graph, which is why the tests can stub the runtime
  without the lifecycle pointing at a real store.
- **An error contract with codes, not prose.** `vibe/api/errors.py` gives every
  failure the same body `{"error": {"code", "message"}}` and one default-status
  map. The 401/403 separation (loopback auth vs `OriginGuard`) is correct and
  the reasoning is documented at the call site.
- **Path confinement that resolves symlinks.** `SessionService.resolve_file`
  and `tools/files._safe_path` both `resolve()` before `is_relative_to`,
  so a symlink escape is rejected; `test_services.py` covers it.
- **The event log's sequence discipline.** Ephemeral frames reserve a real
  monotonic seq without being stored; the SSE route subscribes *before*
  replaying and dedupes by seq. This is the non-obvious part of a
  reconnect-safe stream and it is right.
- **Honest capability degradation.** `read_console_logs`/`screenshot` return
  `None` ("no driver") rather than `""` ("clean"), and `AutoRunPolicy`
  treats `None` as "nothing was read". That distinction is what stops the
  fix-loop from claiming a check it never ran.
- **The TOCTOU-conscious delete ordering** and the pipe-draining dev server
  are both real fixes with their rationale kept next to the code.
- **Test discipline.** 190 backend tests with deterministic stubs, a live
  ASGI/SSE harness, and assertions on observable behaviour.

---

## BE-01 — Unvalidated request bodies answer 500 instead of 4xx — **High**

**Where:** `api/routes/sessions.py:28`, `sessions.py:72`, `api/routes/chat.py:46`.

**What:** Session, message and PATCH bodies are declared `body: dict`, so
FastAPI performs no validation. A missing or malformed field raises
`KeyError`/`TypeError` inside the handler, which the generic `Exception`
handler turns into `500 internal server error`.

**Reproduction** (probe 1):

```
POST /sessions body={}            -> HTTP 500  {"error":{"code":"internal",...}}
POST /sessions body={model:{}}    -> HTTP 500
POST /sessions body={model:{a:1}} -> HTTP 500
POST /sessions/{sid}/messages {}  -> HTTP 500
PATCH /sessions/{sid} {model:{}}  -> HTTP 500
POST /providers {}                -> HTTP 400  (correct — it validates by hand)
```

**Impact:** a client bug, a version skew, or a fuzzer produces a 500 and a
server-side traceback where the contract promises `validation_failed`. It also
means the error taxonomy built in P4 has a hole at exactly the boundary it was
made for. `POST /providers` shows the intended alternative.

**Deliberate?** No. The P4 work introduced `ErrorCode.VALIDATION_FAILED`
precisely for this.

**Fix sketch:** replace `body: dict` with pydantic request models
(`model: ModelRefModel`, `content: str`, optional `attachments: list[...]`).
FastAPI then returns the shaped 422 through `_handle_validation_error`.

---

## BE-02 — The supply-chain allowlist can be bypassed with a package spec — **High**

**Where:** `supply_chain.py:24-32`; consumer `executor/local.py:67-68`.

**What:** `is_allowlisted` reduces an unscoped specifier to the text before the
first `@`:

```python
else:
    name = package.split("@")[0]
return name in ALLOWLIST
```

That is correct for `react@^19` but wrong for every npm **protocol/alias**
specifier, which `pnpm install` understands and which still puts an arbitrary
package on disk.

**Reproduction** (probe 2):

```
is_allowlisted('react@npm:evil-package')  = True
is_allowlisted('react@github:evil/repo')  = True
is_allowlisted('react@file:../evil')      = True
```

**Impact:** the approval gate — the one control that asks a human before an
unknown package is installed — is bypassed by the model (or by content the
model read from generated code) choosing `react@npm:evil-package`. The
executor uses `create_subprocess_exec` (no shell), so this is not command
injection; it is dependency substitution, which is the threat the allowlist
exists for.

**Deliberate?** No.

**Fix sketch:** only treat a specifier as allowlisted when the name exactly
equals an allowlist entry *and* the remainder (if any) is a narrow semver
range. Reject any specifier containing `:` or a protocol prefix, or resolve
the alias and check the resolved name.

---

## BE-03 — The agent has no conversation memory — **High (product)**

**Where:** `api/routes/chat.py:44-47` (one user message is built);
`autorun/policy.py:54-56` (same for fix turns);
`runtime/langgraph.py:98-108` (graph compiled per run, no checkpointer).

**What:** every turn constructs `AgentInput` with exactly one message — the new
user message. Prior turns are persisted in the event log and shown in the UI,
but are never sent to the model.

**Reproduction** (probe 3), two turns over a stub runtime that records
`input.messages`:

```
run 0: messages handed to the model = [('user', 'my name is Ahmad')]
run 1: messages handed to the model = [('user', 'what is my name?')]
history the UI can read: [user, assistant, user, assistant]   # 4 messages
```

**Impact:** the chat looks stateful and is not. "Make the header blue", "undo
that", "add validation to the form you just made" have no referent except
whatever the model can rediscover by reading files. For a chat-driven IDE this
is the difference between iterating and re-prompting from scratch each turn.
The `MessageService` projection that could supply history already exists and is
only wired to `GET /messages`.

**Deliberate?** Not documented. `PLAN.md`/README claim a chat panel and an
auto-fix loop; neither states that the model is stateless across turns.

**Fix sketch:** on `send_message`, project recent history (`MessageService`)
into `AgentInput.messages` ahead of the new turn, bounded by a token/step
budget. `runtime/langgraph._to_lc_message` already handles assistant and tool
messages, so the runtime seam is ready. Alternatively add a LangGraph
checkpointer keyed by `session_id` — but history is already the source of
truth in the event log, so projecting it is the smaller change.

---

## BE-04 — Two concurrent sends both start a run — **High**

**Where:** `api/routes/chat.py:34` (guard) and `chat.py:85` (claim).

**What:** `runs.is_running(sid)` is checked at line 34, but the run is not
claimed until line 85 — after `require_session`, `event_log.append` (a
`to_thread` await), `retitle_from_message`, a bus publish and a workspace
snapshot. Two requests that arrive together both observe "not running".

**Reproduction** (probe 4), two simultaneous POSTs under `httpx.ASGITransport`:

```
run() invocations: 2
statuses: [200, 200]      # an atomic guard gives one 200 and one 409
```

**Impact:** two agent runs write the same workspace and interleave into one
transcript; `RunRegistry.start` overwrites the first handle, so `/abort`
cancels only the second run — the first keeps going with nothing pointing at
it. This is the exact failure the 409 exists to prevent, and it is reachable
by a double-click.

**Deliberate?** No — `CURRENT_STATE.md` states "one agent run per session (a
concurrent send is 409)".

**Fix sketch:** claim the handle immediately after `require_session` (or make
`RunRegistry.begin(sid)` an atomic check-and-set returning a handle or None)
and release it in the existing `finally`.

---

## BE-05 — A timed-out executor command keeps running — **Medium**

**Where:** `executor/local.py:52-66`.

**What:** `asyncio.wait_for(proc.communicate(), timeout)` raises
`TimeoutError`; the handler logs and returns a "timeout" result without
killing the child. Cancelling `communicate()` does not terminate the process.

**Reproduction** (probe 5): run a child that writes a marker after 3 s with a
1 s timeout:

```
tool result: timeout | is_error: True
child still alive 3.5s after the 1s timeout? True
```

**Impact:** a hung `pnpm install` or `build` survives the tool call — it keeps
the workspace files open, keeps consuming CPU/network, and on Windows can
block the delete cascade's `workspace.rename` (which is how BE-06 is
reachable without a user holding a file). Repeated timeouts can stack orphaned
processes.

**Fix sketch:** on timeout, `proc.kill()` (ideally the whole process tree on
Windows) and `await proc.wait()` before returning.

---

## BE-06 — A failed workspace move leaves the session half-torn-down — **Medium**

**Where:** `lifecycle.py:48-70` (`clear` at :58, `rename` at :66,
row delete at :70).

**What:** the cascade clears the event log and drops the executor/approvals
*before* the workspace move. If `rename` fails, the row survives and the
session reappears — with its transcript gone.

**Reproduction** (probe 7): hold a file open inside the session workspace, then
call `SessionLifecycle.delete`:

```
delete raised: PermissionError [WinError 5]
session row still present after failed delete? True
events before=2 after=0
```

**Impact:** a user whose delete fails (open handle, antivirus lock, another
process) is left with a session that looks intact but has lost its chat
history. The docstring promises the failure "leaves the session intact instead
of silently orphaning the files" — the row is intact, the *content* is not.

**Fix sketch:** do the irreversible move first (or on failure, restore what
was cleared); at minimum reorder so `event_log.clear` runs only after the
rename succeeds.

---

## BE-07 — The VIBE_HOST warning cannot be formatted and never appears — **Medium**

**Where:** `api/app.py:47-51`.

**What:** the call passes one `%s` and two positional arguments:

```python
logger.warning(
    "VIBE_HOST=%s: bound beyond loopback; loopback auth still refuses non-local peers,",
    " but every local process can reach this API.",
    settings.host,
)
```

**Reproduction** (probe 6), run the real lifespan with `VIBE_HOST=0.0.0.0`:

```
formatting errors raised: ["TypeError('not all arguments converted during string formatting')"]
records that formatted cleanly: ['vibe ready: ...', 'vibe stopped']
```

stderr receives a `--- Logging error ---` traceback instead of the warning.

**Impact:** the one message designed to tell an operator "you bound this
beyond loopback" is never delivered; the operator gets a stack trace and might
reasonably think the app is broken. It also makes `test_logging.py`'s promise
of a clean single-handler setup incomplete.

**Fix sketch:** one `%s` with one argument, or an f-string. There is no test
for this branch, which is why CI is green.

---

## BE-08 — Auto-run fix turns are neither logged nor broadcast — **Medium**

**Where:** `autorun/policy.py:50-57`.

**What:** `_fix_turn` iterates the runtime's events and discards every one
(`async for _ in ...`). No `event_log.append`, no `event_bus.publish`. By
contrast the main turn logs `user/message`, `assistant/message`,
`tool_call`, `tool_result` and `assistant/error`.

**Impact:** the repository's first architectural rule is "model-visible means
logged". A fix turn is a model call whose output mutates the user's project and
costs tokens (usage *is* recorded), yet it is invisible in the transcript and
in SSE. A user watching a build failure sees files change with no explanation
and cannot audit what the agent did.

**Deliberate?** Not documented. The autorun loop is described in README as
feeding errors back to the agent and fixing them.

**Fix sketch:** route fix-turn events through the same logging/publishing path
as the main turn (a small shared helper in `chat.py`, or move the loop to emit
through the bus).

---

## BE-09 — "No browser driver" is reported when the real cause is "no dev server" — **Low**

**Where:** `tools/executor_tools.py:45-52`, `executor/local.py:127-140`.

**What:** `read_console_logs(url=None)` and `screenshot(url=None)` return
`None`, and the tool turns any `None` into
`"unavailable: this build has no browser driver installed"`. But
`LocalSubprocessExecutor.dev_server_url` is `None` whenever the dev server is
not running, which has nothing to do with a browser driver.

**Impact:** the model is told to give up on browser checks for a reason that
may be false; it may never call `run_dev_server` first. Low because the
auto-run path only reaches this after starting the server.

**Fix sketch:** have the executor distinguish "no server" from "no driver"
(e.g. return a sentinel or let the tool check `dev_server_url` first).

---

## BE-10 — Small contract inconsistencies in the sessions routes — **Low**

**Where:** `api/routes/sessions.py`.

1. `sessions.py:49` `if usage is None` is dead: `Container.build` always
   constructs a `UsageTracker`, so the 404 branch is unreachable and untested.
2. `GET /sessions/{sid}` (`:37-39`) returns `id/title/model` but the list
   endpoint (`:31-36`) also returns `created_at/updated_at`. A client cannot
   get a single session's timestamps.
3. `PATCH` and file writes answer `{"ok": true}` while every other resource
   returns a representation; harmless, but inconsistent.
4. `chat.py:107` puts the raw exception text into a client-visible
   `ApiError(INTERNAL, error)`, which bypasses `_handle_unexpected`'s
   deliberate generic message. A `GraphRecursionError` or a driver message
   reaches the browser verbatim. Local-only, so Low.

---

## BE-11 — `.trash/` has no retention policy — **Low**

**Where:** `lifecycle.py:63-67`; nothing else references `.trash`.

Deleted workspaces are moved to `<workspace>/.trash/<sid>-<timestamp>/` and
never cleaned. Each may contain a full `node_modules` tree. Disk grows without
bound and with no UI to empty it. `workspace.py` correctly hides `.trash`
from listings, so it is invisible.

**Fix sketch:** a retention setting (age/count/size) applied by the same reaper
that stops idle dev servers, or a "empty trash" action.

---

## BE-12 — Pagination and usage are computed over the whole event log — **Low**

**Where:** `services/messages.py:51`, `usage/tracker.py:48-49`.

- `MessageService.page` loads *every* event for the session, projects, then
  slices. `limit`/offset bound the response, not the work.
- `UsageTracker._records` likewise scans all events; `session_total` and
  `session_by_model` each call it, so one `GET /usage` reads the full log
  twice.

At today's session sizes this is invisible; it is O(history) per request and
will show up on long-lived sessions. The event `type` is not indexed for this
purpose.

---

## BE-13 — Import-time `.env` discovery reaches outside the repo — **Info/Low**

**Where:** `config.py:7-34`; called at import.

`_load_dotenv()` walks up to three parent directories from the *current
working directory* at import time and injects any `.env` keys into
`os.environ` (without overwriting existing ones). Two consequences worth
knowing: importing the package has a process-wide side effect, and a `.env` in
an ancestor directory (a user profile, a parent project) silently configures a
vibe install. Since `OPENAI_API_KEY` etc. live here, that is a surprising
precedence chain.

---

## BE-14 — One malformed custom model breaks the model picker for the whole app — **Medium**

**Where:** `api/routes/catalog.py:25`, reachable from
`api/routes/providers.py:44-56`. **Verified by `probes/custom_provider_probe.py`
(`evidence/custom-provider-probe.txt`).**

**What:** the catalog merge indexes the stored model dict directly:

```python
models=[{"id": m["id"], "name": m.get("name", m["id"])} for m in p.models],
```

and `POST /providers` performs no validation of `models`. So the API accepts a
model without an `id` (201), and from then on **every** `GET /catalog` — for
every session and every client — answers 500, taking the ModelPicker down with
it.

**Reproduction:**

```
POST /providers {"name":"New","baseUrl":"http://y","models":[{"name":"no-id"}]}  -> 201
GET  /catalog                                                                     -> 500
GET  /providers                                                                   -> 200
```

**Impact:** a single bad write (the UI's "Add model" row can submit an empty id)
permanently disables model selection until the JSON file is edited by hand.

---

## BE-15 — A corrupt `providers.json` is unrecoverable from the app — **Medium**

**Where:** `providers/custom.py:41-46`. **Verified by the same probe.**

`_load` runs `json.loads(self._path.read_text(...))` with no guard, and `_save`
is a plain `write_text` (not atomic). A truncated file — from an interrupted
write, a full disk, or a hand edit — makes `GET /providers` **and**
`GET /catalog` answer 500 on every request, with no in-app way back.

**Reproduction:** write `{not json` to `<workspace>/providers.json`;
`GET /providers` → 500 and `GET /catalog` → 500.

**Fix sketch:** tolerate an unreadable store by starting empty (log loudly), and
write via a temp file + `os.replace`.

---

## BE-16 — The provider store reads and writes a file on the event loop, unlocked — **Low**

**Where:** `providers/custom.py:41-73`.

Every `list`/`get`/`create`/`update`/`delete` call does synchronous file I/O
directly inside an async handler (no `asyncio.to_thread`), and read-modify-write
is unprotected: two concurrent creates can each load the old map and save its
own, losing one provider. The rest of the persistence layer already gets this
right (sqlite + `to_thread` + a lock), which makes this the odd one out.

---

## BE-17 — The API *can* clear an API key; only the UI cannot — **Info**

**Where:** `api/routes/providers.py:53-58`; `apps/vibe/.../SettingsPanel.tsx:70`.

	exttt{PATCH /providers/{pid} {"apiKey": ""}} → 200 with `key_configured: false`
(probe 2, C4). The README's "stored API key cannot be cleared from the UI" is
therefore a frontend-only gap: the panel sends `apiKey: form.apiKey || undefined`,
and a missing key means "unchanged". Clearing is a one-line UI change
(send `""` explicitly behind a "Clear key" action).

---

## BE-18 — Provider keys are plaintext at the workspace root, but agent-confined — **Info**

**Where:** `container.py:108` → `settings.workspace_dir / "providers.json"`.

Keys are stored in plaintext JSON, like `.env`. Worth recording the boundary
that makes it acceptable: the agent's file tools are confined to
`workspace_dir/<session_id>` (`SessionService.resolve_file`), so the agent
cannot read the sibling `providers.json`, and `to_public` never exposes the
key. Reasonable for a loopback-only local app; it would need attention before
any multi-user or remote deployment.

---

## BE-19 — The agent runs with no system prompt at all — **Medium**

**Where:** `runtime/langgraph.py` (the `"system"` branch in `_to_lc_message`, which no caller
used), `models.py` `AgentInput`.

**What:** nothing ever emits a system message. `AgentInput` had no `system` field and no
caller converted one, so the model's entire instruction set was the tool schemas. Nothing
stated the target stack (React + Vite + TypeScript), that a session owns exactly one
workspace, the install allowlist policy, or any coding convention. Adding conversation
history (BE-03) made this sharper: the model is handed a transcript with no framing.

**Impact:** behaviour drifts with the model and the turn. A model can reach for another
framework, or route around a refused install, with nothing in the prompt to the contrary,
and the drift is invisible in the transcript because there is no instruction text to log.

**Decision (user, 2026-10-11), verbatim:** "add a system prompt and other need it whether in
the config or in the gui".

**Fix:** `vibe/prompts.py` holds `DEFAULT_SYSTEM_PROMPT` and `system_prompt_for()`;
`AgentInput.system` carries it; `LangGraphRuntime.build_messages` puts it first as a
`SystemMessage`; `Settings.system_prompt` (`VIBE_SYSTEM_PROMPT`) overrides the default and a
blank override falls back to it; the chat route and the auto-fix loop both send it.
`tests/test_system_prompt.py` (8 cases) plus the autorun prompt case.

**One deliberate gap, and one gap now closed.** The prompt itself is not written to the event
log: it is static configuration rather than conversation, so a session's log stays readable,
but two sessions under different `VIBE_SYSTEM_PROMPT` values cannot be told apart from their
logs. The GUI half is delivered: `GET /settings` reports the effective prompt and its source,
`PATCH /settings` writes an override to `<workspace>/settings.json` (never the environment, so
the app cannot rewrite its own operator configuration; it applies to the next turn without a
restart, and an empty string clears it), and `SettingsPanel.tsx` renders the field with a source
label (`SystemPrompt.test.tsx`, 5 cases). The earlier note here called the field open; it
landed in R3 and is green in the release gate.

**Risk to re-check:** it changes behaviour on every model, so the live E2E re-run in R7 must
confirm the loop still builds an app with a prompt in place.

## BE-20 — A workspace held open makes `DELETE` answer 500 and hides that the session survived — **Medium**

Found by the R7 acceptance run, not by the original review: `scripts/acceptance-local.ps1`
step 6 failed twice with `DELETE /sessions/{sid}` → `500 {"error":{"code":"internal",
"message":"internal server error"}}`, `.trash/` empty and the session row still present.
The same two runs showed a preview process still alive on its own port at that point.

**Cause, reproduced:** renaming a directory on Windows fails with `WinError 5` while any
process still holds a file inside it, and `lifecycle.delete()` called `workspace.rename(trash)`
with nothing catching the `OSError`. The mechanism is three lines:

```python
d = Path(tempfile.mkdtemp()); w = d / "ws"; w.mkdir()
f = open(w / "locked.txt", "w")          # any open handle, e.g. a live vite/node process
w.rename(d / ".trash" / "s-1")           # PermissionError: [WinError 5] Access is denied
```

The ordering the R1 fix put in place did its job — the transcript and the row were still
there — but the user could not tell why, and a 500 on a delete reads as "the app is broken"
rather than "close the program that has your files open".

**Fix (R7):** `lifecycle.move_workspace_to_trash()` retries the rename five times at 0.2 s
(the dev server this delete just stopped needs a moment to release its handles) and then
raises `WorkspaceBusyError` naming the directory and the remedy; `api/routes/sessions.py`
maps it to `409 workspace_busy` (new `ErrorCode.WORKSPACE_BUSY`). The session, its files and
its transcript are all left intact so the delete can simply be retried.

**Evidence:** `artifacts/hardening-r7-delete-busy.txt` (mechanism repro, RED/GREEN, suite).
Regression tests: `tests/test_delete_cascade.py` (a move that fails once is retried; a
permanent lock is a named error and keeps events, row and files) and
`tests/test_api.py::test_delete_says_the_workspace_is_busy_instead_of_failing_generically`
(409, not 500, and the session still reads back).

## BE-21 — The rotating log file is never written unless the user names one — **Medium**

**Where:** `services/vibe/src/vibe/config.py` (`_LOG_OFF_VALUES`, `Settings.from_env`).

**What:** `config.py` documents its own contract — "Logging to a file is on by
default, under the workspace: a user who is asked 'send me the log' must not
have to hunt in a console that was already closed" — and both `README.md` and
`docs/guides/local-setup.md` name `<workspace_dir>/logs/vibe.log` as the default
path with `VIBE_LOG_FILE=off` as the way out. In reality the file only appeared
if the user set `VIBE_LOG_FILE` to an explicit path. `_LOG_OFF_VALUES` contained
the empty string, so `Settings.from_env()` read an *unset* variable as a
deliberate off value: `log_to_file=False`, `log_file=None`, and
`configure_logging` installed one stderr handler and nothing else.

**Why it survived review:** the tests covered the two paths that worked (an
explicit path, and `off`) plus a directly constructed `Settings`, whose dataclass
default *is* `log_to_file=True`. The one combination a real user has —
`from_env()` with nothing set — was never exercised. The R5-T5 evidence is
correct about the handler and wrong about the default.

**Blast radius:** the console keeps working and the app never fails, so nothing
looks broken. The cost lands on the support path the comment is about: a user
asked for a log has no file to send, and an unexpected 500 leaves no traceback
anywhere — which is exactly how this was found (a concurrent acceptance run's
`error id 2c60107f` had no log to explain it).

**Fix:** drop `""` from `_LOG_OFF_VALUES`. `off`/`none`/`false`/`no`/`0` still
disable the file; an unset variable now falls through to `__post_init__`, which
resolves `log_file` to `<workspace_dir>/logs/vibe.log`.

**Evidence:** `artifacts/hardening-r7-log-default.txt` (the RED probe, the fix,
the end-to-end server writing the file, 459 passed, ruff clean). Regression test:
`tests/test_logging_setup.py::test_an_unset_vibe_log_file_still_writes_the_default_file`,
which goes through `Settings.from_env()` rather than a hand-built `Settings`.

**Follow-up - resolved by BE-22:** the 500 that led here was not a separate
mystery. Its error id `2c60107f` appears in the same run's process stderr with
`sqlite3.IntegrityError: UNIQUE constraint failed: events.session_id, events.seq` - two acceptance
runs sharing one temp workspace and one port is exactly the overlap BE-22 needs. This finding
explains why the *workspace* log had nothing to offer: the traceback existed only on stderr, which the
acceptance script redirects to a file.
## BE-22 - A second event-log allocator turns the app's primary action into a 500 - **High**

Found by the R7 acceptance re-run, from the one artifact the earlier runs left behind: the process
stderr of the run in which BE-21 was found. Step 3's `POST /sessions/{sid}/messages` answered
`500 {"error":{"code":"internal","message":"internal server error"}}`, and the stderr names the cause
in one line:

    vibe.api.routes.chat: run failed for session 7bce05d1cce4 (error id 2c60107f)
    sqlite3.IntegrityError: UNIQUE constraint failed: events.session_id, events.seq

**Cause, reproduced:** `EventLog.next_seq()` hands out numbers from an in-memory per-session counter
(`self._seq`) seeded once from `_max_seq()` (`SELECT COALESCE(MAX(seq),0)`), and `append()` reserved a
number and then inserted it. Streaming chunks and turn boundaries take numbers through `next_seq()`
without storing a row - deliberately, since one row per token would bloat the log - so the counter
cannot simply mirror the table. Any second allocator that stores a durable row for the same session
makes the two counters diverge: a second `EventLog` instance, or a second process sharing the SQLite
workspace after a restart overlap. The loser's INSERT violated `PRIMARY KEY (session_id, seq)`, and
the raw `sqlite3.IntegrityError` propagated out of `UsageTracker.record -> EventLog.append -> EventLog._insert` and killed the turn. The reproduction is deterministic: two `EventLog` objects over
one database, both reserving seq 1, the first storing it - the second's stale counter then picks 2,
which is already durable.

**Risk:** this is the only finding in the review that takes a normal user action down completely, and
it is timing-dependent, which is why every other run was green. It also hides its own cause from the
user: a 500 with an error id reads as "the app is broken", not "one event could not be numbered".

**Fix (R7):** `_insert` catches `sqlite3.IntegrityError`, and only when the violation is the events
primary key (`sqlite_errorname == SQLITE_CONSTRAINT_PRIMARYKEY`, with the message as a fallback for
builds that report a composite key as UNIQUE), re-seeds that session's counter to
`max(in-memory, _max_seq())` under the existing lock and retries a fresh number above the durable
maximum, bounded by `_INSERT_ATTEMPTS = 3`; past the bound it raises the named `EventSeqConflict`.
Non-PK IntegrityErrors are re-raised untouched, the UNIQUE constraint is unchanged, and `append()` now
returns the number actually stored. Because the re-seed takes the maximum, a seq a client has already
seen is never handed out again.

**Limitation:** the live run's second writer was not observed directly - the collision is reproduced
over the same database by the same mechanism - and `EventSeqConflict` still reaches the client through
the chat route's generic handler as a 500 with an error id. That is a named failure instead of a raw
SQLite error and no durable event is ever renumbered, but mapping it to a distinct code remains open.

**Evidence:** `artifacts/hardening-be22-seq-race.txt` (RED then GREEN on the new tests, the diff, the
suite). Regression tests in `services/vibe/tests/test_events.py` (two `EventLog` objects over one
database: the loser retries above the durable maximum; a non-PK IntegrityError still propagates).
Verified at the gate after the fix: backend **459 passed**, ruff clean,
`artifacts/hardening-gate-final-backend.txt`.

## BE-23 - in prod mode the OriginGuard refuses the app's own UI, so no session can be created - **High**

Found by the R7 browser verification: M6 failed (the palette advertised `New session ... Ctrl Alt N`, the
press left the sidebar at `No sessions yet` and `GET /sessions` at 0; the control case - `Ctrl+K` opening
the same palette - proved key delivery, the palette's own entry also produced 0, and the empty-state
button surfaced `origin not allowed` in the UI), and every other UI check blocked behind it. The instance
was real: `VIBE_MODE=prod`, port 7322, a temp workspace, `agent-browser` driving the served SPA.

**Cause.** `app.py` installs `OriginGuard` with `settings.cors_origins`, whose default is
`DEFAULT_CORS_ORIGINS` - `http://localhost:5173,http://127.0.0.1:5173`, the Vite dev origins. In `prod`
mode the app serves the SPA itself, so the page's own `Origin` is `http://127.0.0.1:<port>`; no fixed
default can name a port chosen at startup, so every POST/PUT/PATCH/DELETE from the UI was answered
`403 forbidden_origin`. The re-run on the fixed build settles the follow-up question: M6 passes from all
three entry points (`Ctrl+Alt+N`, the palette entry that advertises it, and the empty-state button), so the
binding was never broken - the 403 was the whole failure.

**Scope: why the packaged path hid it.** The symptom is total - the UI cannot create a session - so the finding is High even though `start.bat` masks it: `start.bat` computes the free port and exports `VIBE_CORS_ORIGINS`
containing `http://127.0.0.1:%VIBE_PORT%`, so the packaged path worked. The defect hit every other prod
invocation - including the bare `python -m vibe serve` that section 6 of the guide presented as
equivalent to the launchers, and the browser harness. Neither green suite could catch it: pytest's client
sends no `Origin` unless a test asks for one, and `Invoke-WebRequest` never sends one.

**Fix (R7):** `OriginGuard` now also trusts a request that is same-origin with its own `Host` -
`_same_origin()` parses both sides (`urlsplit`, never a string prefix), takes the scheme from the ASGI
scope, applies the scheme's default port when one is missing, and compares hostnames case-insensitively.
The allowlist stays for the dev cross-origin split, `start.bat` is unchanged, a missing `Origin` is still
allowed, and reads are still exempt. Five tests in `services/vibe/tests/test_auth.py` cover the prod case
(an explicit port accepted), a different port on the same host refused, default-port normalization, a
scheme mismatch refused, and `localhost` not treated as `127.0.0.1`. Independently re-proved on a real
server with `VIBE_CORS_ORIGINS` unset: the same-origin `POST /sessions` answered **201**, a foreign
Origin **403 forbidden_origin**, and a request with no Origin 201.

**Limitation:** same-origin trust is the standard CSRF rule, but it does not address DNS rebinding (there
the browser's own `Host` is attacker-controlled too); the loopback token and the binding to 127.0.0.1
remain that control. The scheme comes from the ASGI scope, so a TLS-terminating proxy would need the
scope to say `https`, or the operator to list the public origin in `VIBE_CORS_ORIGINS`. The doc half of
the same trap is closed too: section 6 of the guide no longer claims the bare module command is equivalent
to the launchers - it states the mode that command needs and why.

**Evidence:** `artifacts/hardening-r7-browser-checks.txt` (the failure and six screenshots),
`artifacts/hardening-be23-prod-origin.txt` (RED then GREEN, the diff and the suite),
`artifacts/hardening-be23-prod-origin-orchestrator.txt` (the real-server transcript),
`docs/guides/local-setup.md` section 6.

## BE-24 - `vibe --help` promised quarantine for the whole store but `repair` leaves a corrupt database alone - **Low**

**Found by** the R5-T7 CLI smoke run while the R7 browser re-check was in flight: the release gate runs
`vibe doctor`, never `vibe backup` or `vibe repair`, so this help text had never been read against the
behaviour it describes.

**What the help said:** `repair  check the local store and quarantine anything unreadable`. Observed per
target: an unreadable `providers.json` **is** moved aside (`maintenance.py`, to
`providers.json.corrupt-<timestamp>`, original bytes kept), while an unreadable database is reported and
deliberately left in place - `FAILED sessions.db failed integrity_check and was left untouched`, exit 1,
`nothing was deleted; the unusable files are still in the workspace`. The implementation is the safe
choice (quarantining a database would silently start the app on an empty store), so the text is what
changed.

**Fix:** the CLI help and the `repair()` docstring now name the one target they can move -
`check the local store, re-run migrations, and quarantine an unreadable providers file`.

**Evidence:** `artifacts/hardening-cli-smoke.txt` (fresh workspace; a populated one backed up through the
SQLite backup API with no `-wal`/`-shm` sidecars; the corrupt-database negative case; and a partial backup
that refuses to report success), plus `services/vibe/src/vibe/__main__.py:27` and
`services/vibe/src/vibe/maintenance.py:141`. Ruff clean and 74 tests green in `test_maintenance.py`,
`test_doctor.py`, `test_custom_providers.py` and `test_settings_store.py` after the change.

## Cross-cutting note: the validates-nothing pattern

BE-01 and BE-13 are the same theme from two directions: the edges of the
system — HTTP input and process environment — are the two places where the
codebase's otherwise strong explicitness gives way to `dict` and `os.environ`.
Everything between them (seams, errors, projection, lifecycle) is deliberate
and tested. A reviewer's recommended sequencing is: BE-04 and BE-05 first
(correctness/resources), then BE-01 and BE-02 (the security/contract edges),
then BE-03 (the product gap), then the rest as hygiene.
