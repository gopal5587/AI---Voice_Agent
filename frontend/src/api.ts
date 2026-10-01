export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const post = <T,>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });

export interface PublicConfig {
  vapi_public_key: string | null;
  vapi_assistants: Record<string, string>;
  llm_enabled: boolean;
  embedder: string;
  asr_provider: string;
  retrieval_min_score: number;
}

export interface AgentInfo {
  key: string;
  name: string;
  description: string;
  languages: string[];
  voice_lang: Record<string, string>;
  market: string;
  vapi_assistant_id: string | null;
}

export interface AgentReply {
  session_id: string;
  text: string;
  end_call: boolean;
  intent: string;
  citations: string[];
  lang: string;
  voice_lang: string;
  latency_ms: number | null;
  state: {
    stage: string;
    slots: Record<string, unknown>;
    pending: string | null;
    outcome: Record<string, unknown> | null;
    lang: string;
    dialects: string[];
  };
}

export interface KbHit {
  record_id: string;
  title: string;
  content: string;
  category: string;
  market: string;
  source_uri: string;
  source_locator: string;
  version: string;
  status: string;
  score: number;
  confidence: number;
  bm25: number;
  dense: number;
  term_coverage: number;
  citation: string;
}

export interface KbSearchResult {
  query: string;
  status: "OK" | "INSUFFICIENT_EVIDENCE";
  latency_ms: number;
  hits: KbHit[];
}
