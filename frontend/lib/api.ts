// Typed client for the Ironvale API. The response shape mirrors the backend's AskResponse contract.
export const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Route = "docs" | "data" | "graph" | "out_of_scope";
export type Status = "answered" | "not_found" | "out_of_scope" | "error";

export interface Citation {
  n: number; doc_id: string; title: string; section?: string | null; page?: number | null;
  version?: string | null; effective_date?: string | null; superseded: boolean; chunk_id?: string | null;
}
export interface SqlResult {
  query: string; columns: string[]; rows: (string | number | null)[][]; row_count: number;
  chart: { type: "bar" | "line"; x: string; y: string } | null;
}
export interface GraphResult { template: string; params: Record<string, string>; paths: string[][]; }
export interface AskResponse {
  request_id: string; user_id: string; role: string; question: string; rewritten_query: string;
  route: Route; status: Status; answer: string; citations: Citation[];
  sql: SqlResult | null; graph: GraphResult | null;
  pipeline: { timings_ms?: Record<string, number>; trace_id?: string; model?: string; error_class?: string | null;
              top_rerank_score?: number; retrieved?: Record<string, number> };
}
export interface DemoUser { user_id: string; name: string; role: string; scope: string; }
export interface Turn { role: "user" | "assistant"; content: string; }

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<T>;
}

export const getUsers = () => fetch(`${API}/v1/users`).then((r) => j<DemoUser[]>(r));
export const ask = (user_id: string, question: string, history: Turn[]) =>
  fetch(`${API}/v1/ask`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id, question, history }) }).then((r) => j<AskResponse>(r));
export const getChunk = (chunk_id: string, user_id: string) =>
  fetch(`${API}/v1/chunks/${encodeURIComponent(chunk_id)}?user_id=${encodeURIComponent(user_id)}`).then((r) =>
    j<{ doc_id: string; title: string; section: string | null; page: number | null; version: string;
        effective_date: string; superseded: boolean; source: string; text: string }>(r));
export const sendFeedback = (trace_id: string, value: 0 | 1) =>
  fetch(`${API}/v1/feedback`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trace_id, value }) }).then((r) => j<{ recorded: boolean }>(r));
export const getEval = () => fetch(`${API}/v1/eval`).then((r) => j<EvalData>(r));

export interface EvalRun { run_id: string; created_at: string; git_commit: string; prompt_version: string; model: string;
  metrics: Record<string, any>; }
export interface EvalData { runs: EvalRun[]; failed: any[]; langfuse_host: string; }
