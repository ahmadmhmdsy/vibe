export interface Session {
  id: string;
  title: string;
  model: { provider_id: string; model_id: string };
  /** Optional: both `GET /sessions` and `GET /sessions/{id}` return these
   * (R3-T6). Optional so an optimistic client-side session is valid before the
   * server echoes it back. */
  created_at?: string;
  updated_at?: string;
}

/** Where a new session's project comes from (M8/C1).
 *
 * `empty` is what every client sent before this existed; the backend defaults
 * to it too, so the two cannot drift. `path` is a folder on the *server's*
 * machine — a browser cannot hand over a local directory — and `url` is a git
 * repository. A folder is opened in place, never moved or copied.
 */
export type ProjectSource =
  | { kind: "empty" }
  | { kind: "template" }
  | { kind: "folder"; path: string }
  | { kind: "git"; url: string };

/** What the created session's workspace turned out to be.
 * `stack` is "unknown" for anything the executor cannot install and run. */
export interface ProjectInfo {
  stack: string;
  framework: string;
  start_command: string | null;
  language: string | null;
}

export interface ProviderInfo {
  id: string;
  name: string;
  capabilities: { tool_support: boolean; vision: boolean };
  models: { id: string; name: string }[];
  key_configured: boolean;
}

/** GET/PATCH /settings (BE-19).
 *
 * `source` names the layer that won: the environment (`VIBE_SYSTEM_PROMPT`),
 * the prompt saved in this workspace's settings.json, or the built-in default.
 * The Settings panel must not offer a field the environment would ignore, so it
 * disables the textarea when `source` is "env".
 */
export interface SystemPromptSettings {
  system_prompt: {
    /** The raw environment value; "" when the environment set nothing. */
    configured: string;
    /** What the model will actually receive. */
    effective: string;
    default: string;
    source: "default" | "file" | "env";
  };
}

/** The one place a frontend API origin is built.
 *
 * Both the REST calls below and the SSE client in ./sse read this, so the app
 * has exactly one default origin. A production build is served by the API
 * process itself (R5-T3), so its default is same-origin: a relative URL keeps
 * working when the chosen port is not 7321. Development keeps the absolute
 * default because there is no Vite proxy for /sessions; `start.bat dev` sets
 * VITE_API_URL explicitly, so only a bare `pnpm run dev` relies on this.
 */
export const API_BASE =
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "" : "http://localhost:7321");

/** Error thrown by every api method on a non-2xx response.
 *
 * `code` is the backend's stable error identifier (see vibe/api/errors.py) and is
 * the part a caller should branch on: `status` is transport and `message` is prose
 * that may change. It is undefined when the failure never reached the app at all
 * (a network error, or a proxy answering on its own).
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Turn a failed response into an ApiError, reading the shared error body.
 * Every failure the app raises is `{"error": {"code", "message"}}`, but a proxy
 * or a crashed worker answers in its own shape, so the parse is allowed to fail. */
async function toApiError(resp: Response): Promise<ApiError> {
  try {
    const parsed = (await resp.json()) as { error?: { code?: string; message?: string } };
    const detail = parsed?.error;
    if (detail?.message) return new ApiError(detail.message, resp.status, detail.code);
  } catch {
    // Not our shape; fall through to the generic message.
  }
  return new ApiError(`API error: ${resp.status}`, resp.status);
}

/** Parse a successful response.
 *
 * A 204 -- every delete -- carries no body at all, and `resp.json()` rejects on an
 * empty stream, so a delete used to report a SyntaxError for a request the server
 * had already carried out. */
async function readBody<T>(resp: Response): Promise<T> {
  if (resp.status === 204 || resp.status === 205) return undefined as T;
  const text = await resp.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function reqWithHeaders<T>(
  path: string,
  init?: RequestInit
): Promise<{ data: T; headers: Headers }> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) throw await toApiError(resp);
  return { data: await readBody<T>(resp), headers: resp.headers };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  return (await reqWithHeaders<T>(path, init)).data;
}

/** Encode a workspace-relative path for a URL, keeping the "/" separators.
 * A filename containing "#" or "?" silently truncated the request before. */
function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}

export const api = {
  /** Create a session. `source` defaults to an empty workspace, which is what
   * every caller that only passes a model gets. */
  createSession: (
    model: { provider_id: string; model_id: string },
    source: ProjectSource = { kind: "empty" }
  ) =>
    req<{ id: string; project: ProjectInfo }>("/sessions", {
      method: "POST",
      body: JSON.stringify({ model, source }),
    }),
  listSessions: () => req<Session[]>("/sessions"),
  getSession: (id: string) => req<Session>(`/sessions/${id}`),
  renameSession: (id: string, title: string) =>
    req<{ ok: true }>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  setSessionModel: (id: string, model: { provider_id: string; model_id: string }) =>
    req<{ ok: true }>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ model }) }),
  deleteSession: (id: string) => req<void>(`/sessions/${id}`, { method: "DELETE" }),
  sendMessage: (id: string, content: string, attachments: Attachment[] = []) =>
    req<{ content: string; aborted: boolean }>(`/sessions/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, attachments }),
    }),
  /** Cancel the in-flight turn for this session. */
  abortSession: (id: string) =>
    req<{ aborted: boolean }>(`/sessions/${id}/abort`, { method: "POST" }),
  getCatalog: () => req<ProviderInfo[]>("/catalog"),
  getSettings: () => req<SystemPromptSettings>("/settings"),
  /** Save the workspace system prompt; an empty string clears the override. */
  setSystemPrompt: (systemPrompt: string) =>
    req<SystemPromptSettings>("/settings", {
      method: "PATCH",
      body: JSON.stringify({ system_prompt: systemPrompt }),
    }),
  listProviders: () => req<CustomProvider[]>("/providers"),
  createProvider: (p: { name: string; baseUrl: string; apiKey?: string; models: CustomModel[] }) =>
    req<CustomProvider>("/providers", { method: "POST", body: JSON.stringify(p) }),
  updateProvider: (
    id: string,
    changes: Partial<{ name: string; baseUrl: string; apiKey: string; models: CustomModel[] }>
  ) => req<CustomProvider>(`/providers/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  deleteProvider: (id: string) => req<void>(`/providers/${id}`, { method: "DELETE" }),
  listApprovals: (sid: string) => req<Approval[]>(`/sessions/${sid}/approvals`),
  getUsage: (sid: string) => req<UsageStats>(`/sessions/${sid}/usage`),
  /** One page of history, newest last.
   * `total` is the session's whole message count, so a caller can tell whether
   * paging further back is worthwhile. */
  getMessages: async (
    sid: string,
    opts: { limit?: number; offset?: number } = {}
  ): Promise<MessagePage> => {
    const q = new URLSearchParams();
    if (opts.limit !== undefined) q.set("limit", String(opts.limit));
    if (opts.offset) q.set("offset", String(opts.offset));
    const qs = q.toString();
    const suffix = qs ? "?" + qs : "";
    const { data, headers } = await reqWithHeaders<Message[]>(`/sessions/${sid}/messages${suffix}`);
    // The count travels in a header so this endpoint keeps returning the same
    // bare array as every other collection in the API.
    return { messages: data, total: Number(headers.get("X-Total-Count") ?? data.length) };
  },
  getPreview: (sid: string) =>
    req<{ url: string | null; is_running: boolean }>(`/sessions/${sid}/preview`),
  runPreview: (sid: string) =>
    req<{ url: string; is_running: boolean }>(`/sessions/${sid}/preview/run`, { method: "POST" }),
  stopPreview: (sid: string) =>
    req<{ url: null; is_running: false }>(`/sessions/${sid}/preview/stop`, { method: "POST" }),
  listFiles: (sid: string) => req<string[]>(`/sessions/${sid}/files`),
  readFile: (sid: string, path: string) =>
    req<{ path: string; content: string }>(`/sessions/${sid}/files/${encodePath(path)}`),
  writeFile: (sid: string, path: string, content: string) =>
    req<{ ok: true }>(`/sessions/${sid}/files/${encodePath(path)}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  approve: (aid: string) => req<{ ok: true }>(`/approvals/${aid}/approve`, { method: "POST" }),
  deny: (aid: string) => req<{ ok: true }>(`/approvals/${aid}/deny`, { method: "POST" }),

  // --- source control (M8/C2) -------------------------------------------
  // One session's workspace. `is_repo: false` is an answer, not an error: the
  // panel offers to create a repository instead of showing a failure.
  vcsStatus: (sid: string) => req<VcsStatus>(`/sessions/${sid}/vcs`),
  vcsInit: (sid: string) =>
    req<{ branch: string | null }>(`/sessions/${sid}/vcs/init`, { method: "POST" }),
  vcsDiff: async (sid: string, opts: { path?: string; staged?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (opts.path) q.set("path", opts.path);
    if (opts.staged) q.set("staged", "true");
    const qs = q.toString();
    return req<{ diff: string; truncated: boolean }>(
      `/sessions/${sid}/vcs/diff${qs ? "?" + qs : ""}`
    );
  },
  /** `committed: false` means the workspace was already clean -- the agent had
   *  nothing new on disk -- not that the commit failed. */
  vcsCommit: (sid: string, message: string) =>
    req<{ sha: string | null; committed: boolean }>(`/sessions/${sid}/vcs/commit`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  vcsLog: (sid: string, limit = 20) => req<VcsCommit[]>(`/sessions/${sid}/vcs/log?limit=${limit}`),
  vcsBranch: (sid: string, name: string, create = false) =>
    req<{ branch: string }>(`/sessions/${sid}/vcs/branch`, {
      method: "POST",
      body: JSON.stringify({ name, create }),
    }),
};

/** A path git reports as changed. `status` is git's two-character code. */
export interface VcsFile {
  path: string;
  status: string;
  staged: boolean;
}

export interface VcsStatus {
  is_repo: boolean;
  branch: string | null;
  files: VcsFile[];
}

export interface VcsCommit {
  sha: string;
  subject: string;
  author: string;
  date: string;
}

export interface Approval {
  id: string;
  session_id: string;
  packages: string[];
  status: "pending" | "approved" | "denied";
  created_at: string;
}

export interface Attachment {
  name: string;
  content_type: string;
  data_base64: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface MessagePage {
  messages: Message[];
  /** How many messages the session holds in total, not just in this page. */
  total: number;
}

export interface UsageStats {
  session_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_cache_write_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  steps: number;
  by_model: Array<{
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
    cached_tokens?: number;
    cache_write_tokens?: number;
    steps?: number;
  }>;
}

export interface CustomModel {
  id: string;
  name: string;
  protocol: "openai-chat" | "openai-responses" | "anthropic-messages";
}

export interface CustomProvider {
  id: string;
  name: string;
  baseUrl: string;
  models: CustomModel[];
  key_configured: boolean;
}
