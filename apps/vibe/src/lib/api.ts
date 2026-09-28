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
}

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json() as Promise<T>;
}

export const api = {
  createSession: (model: { provider_id: string; model_id: string }) =>
    req<{ id: string }>("/sessions", { method: "POST", body: JSON.stringify({ model }) }),
  listSessions: () => req<Session[]>("/sessions"),
  getSession: (id: string) => req<Session>(`/sessions/${id}`),
  renameSession: (id: string, title: string) =>
    req<{ ok: true }>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteSession: (id: string) =>
    req<void>(`/sessions/${id}`, { method: "DELETE" }),
  sendMessage: (id: string, content: string) =>
    req<{ content: string }>(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  getCatalog: () => req<ProviderInfo[]>("/catalog"),
};
