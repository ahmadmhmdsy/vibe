export interface Session {
  id: string;
  title: string;
  model: { provider_id: string; model_id: string };
  created_at: string;
  updated_at: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  capabilities: { tool_support: boolean; vision: boolean };
  models: { id: string; name: string }[];
  key_configured: boolean;
}

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:7321";

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
    readonly code?: string,
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
  init?: RequestInit,
): Promise<{ data: T; headers: Headers }> {
  const resp = await fetch(`${BASE}${path}`, {
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
  createSession: (model: { provider_id: string; model_id: string }) =>
    req<{ id: string }>("/sessions", { method: "POST", body: JSON.stringify({ model }) }),
  listSessions: () => req<Session[]>("/sessions"),
  getSession: (id: string) => req<Session>(`/sessions/${id}`),
  renameSession: (id: string, title: string) =>
    req<{ ok: true }>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  setSessionModel: (id: string, model: { provider_id: string; model_id: string }) =>
    req<{ ok: true }>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ model }) }),
  deleteSession: (id: string) =>
    req<void>(`/sessions/${id}`, { method: "DELETE" }),
  sendMessage: (id: string, content: string, attachments: Attachment[] = []) =>
    req<{ content: string; aborted: boolean }>(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content, attachments }) }),
  /** Cancel the in-flight turn for this session. */
  abortSession: (id: string) =>
    req<{ aborted: boolean }>(`/sessions/${id}/abort`, { method: "POST" }),
  getCatalog: () => req<ProviderInfo[]>("/catalog"),
  listProviders: () => req<CustomProvider[]>("/providers"),
  createProvider: (p: { name: string; baseUrl: string; apiKey?: string; models: CustomModel[] }) =>
    req<CustomProvider>("/providers", { method: "POST", body: JSON.stringify(p) }),
  updateProvider: (id: string, changes: Partial<{ name: string; baseUrl: string; apiKey: string; models: CustomModel[] }>) =>
    req<CustomProvider>(`/providers/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  deleteProvider: (id: string) =>
    req<void>(`/providers/${id}`, { method: "DELETE" }),
  listApprovals: (sid: string) => req<Approval[]>(`/sessions/${sid}/approvals`),
  getUsage: (sid: string) => req<UsageStats>(`/sessions/${sid}/usage`),
  /** One page of history, newest last.
   * `total` is the session's whole message count, so a caller can tell whether
   * paging further back is worthwhile. */
  getMessages: async (
    sid: string,
    opts: { limit?: number; offset?: number } = {},
  ): Promise<MessagePage> => {
    const q = new URLSearchParams();
    if (opts.limit !== undefined) q.set("limit", String(opts.limit));
    if (opts.offset) q.set("offset", String(opts.offset));
    const qs = q.toString();
    const suffix = qs ? "?" + qs : "";
    const { data, headers } = await reqWithHeaders<Message[]>(
      `/sessions/${sid}/messages${suffix}`,
    );
    // The count travels in a header so this endpoint keeps returning the same
    // bare array as every other collection in the API.
    return { messages: data, total: Number(headers.get("X-Total-Count") ?? data.length) };
  },
  getPreview: (sid: string) => req<{ url: string | null; is_running: boolean }>(`/sessions/${sid}/preview`),
  runPreview: (sid: string) => req<{ url: string; is_running: boolean }>(`/sessions/${sid}/preview/run`, { method: "POST" }),
  stopPreview: (sid: string) => req<{ url: null; is_running: false }>(`/sessions/${sid}/preview/stop`, { method: "POST" }),
  listFiles: (sid: string) => req<string[]>(`/sessions/${sid}/files`),
  readFile: (sid: string, path: string) => req<{ path: string; content: string }>(`/sessions/${sid}/files/${encodePath(path)}`),
  writeFile: (sid: string, path: string, content: string) =>
    req<{ ok: true }>(`/sessions/${sid}/files/${encodePath(path)}`, { method: "PUT", body: JSON.stringify({ content }) }),
  approve: (aid: string) => req<{ ok: true }>(`/approvals/${aid}/approve`, { method: "POST" }),
  deny: (aid: string) => req<{ ok: true }>(`/approvals/${aid}/deny`, { method: "POST" }),
};

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
