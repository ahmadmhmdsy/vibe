import type { StreamEvent } from "./sse";

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

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Error thrown by every api method on a non-2xx response. Carries the HTTP status. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) throw new ApiError(`API error: ${resp.status}`, resp.status);
  return resp.json() as Promise<T>;
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
    req<{ content: string }>(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content, attachments }) }),
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
  listFiles: (sid: string) => req<string[]>(`/sessions/${sid}/files`),
  readFile: (sid: string, path: string) => req<{ path: string; content: string }>(`/sessions/${sid}/files/${path}`),
  writeFile: (sid: string, path: string, content: string) =>
    req<{ ok: true }>(`/sessions/${sid}/files/${path}`, { method: "PUT", body: JSON.stringify({ content }) }),
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

export interface UsageStats {
  session_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_cache_write_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  steps: number;
  by_model: Array<{ provider: string; model: string; input_tokens: number; output_tokens: number; total_tokens: number; cost_usd: number }>;
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
