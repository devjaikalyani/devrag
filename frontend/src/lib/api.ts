import { toast } from "sonner";
import type { QueryResponse, IndexStats } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

async function fetchJSON<T>(
  path: string,
  options?: RequestInit,
  silent = false
): Promise<T> {
  const authHeader: Record<string, string> = API_KEY ? { "X-API-Key": API_KEY } : {};
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeader, ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    if (!silent) toast.error(detail);
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ── Health ────────────────────────────────────────────────────────────────

export async function getHealth() {
  return fetchJSON<{ status: string; active_key: string | null; total_chunks: number }>(
    "/health"
  );
}

// ── Index / Repos ─────────────────────────────────────────────────────────

export async function getIndexStats(): Promise<IndexStats> {
  return fetchJSON<IndexStats>("/index/stats");
}

export async function switchRepo(key: string) {
  return fetchJSON<{ status: string; active_key: string }>(
    "/repo/switch",
    { method: "POST", body: JSON.stringify({ key }) }
  );
}

export async function deleteRepo(key: string) {
  return fetchJSON<{ status: string; message: string }>(
    `/repo/${encodeURIComponent(key)}`,
    { method: "DELETE" }
  );
}

// ── Ingest ────────────────────────────────────────────────────────────────

export interface IngestResult {
  status: string;
  key?: string;
  new_chunks?: number;
  total_chunks?: number;
  display_name?: string;
  reason?: string;
}

export async function ingestGitHub(url: string, branch = "main"): Promise<IngestResult> {
  return fetchJSON<IngestResult>(
    "/ingest/github",
    { method: "POST", body: JSON.stringify({ url, branch }) }
  );
}

export async function ingestDirectory(path: string): Promise<IngestResult> {
  return fetchJSON<IngestResult>(
    "/ingest/directory",
    { method: "POST", body: JSON.stringify({ path }) }
  );
}

export async function ingestText(text: string, sourceName = "inline"): Promise<IngestResult> {
  return fetchJSON<IngestResult>(
    "/ingest/text",
    { method: "POST", body: JSON.stringify({ text, source_name: sourceName }) }
  );
}

// ── Query ─────────────────────────────────────────────────────────────────

export async function queryRepo(
  question: string,
  checkFaithfulness = true
): Promise<QueryResponse> {
  return fetchJSON<QueryResponse>(
    "/query",
    { method: "POST", body: JSON.stringify({ question, check_faithfulness: checkFaithfulness }) }
  );
}

export async function streamQuery(
  question: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: string) => void
): Promise<() => void> {
  // EventSource cannot send headers, so the API key rides as a query param
  const auth = API_KEY ? `&api_key=${encodeURIComponent(API_KEY)}` : "";
  const url = `${BASE}/query/stream?question=${encodeURIComponent(question)}${auth}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    if (e.data === "[DONE]") {
      es.close();
      onDone();
    } else {
      onToken(e.data);
    }
  };

  es.onerror = () => {
    es.close();
    onError("Stream connection failed");
  };

  return () => es.close();
}

// ── History ───────────────────────────────────────────────────────────────

export async function clearHistory() {
  return fetchJSON<{ status: string }>("/history", { method: "DELETE" });
}

export async function clearAll() {
  return fetchJSON<{ status: string; message: string }>("/index", { method: "DELETE" });
}

// ── Agent runs ────────────────────────────────────────────────────────────

export interface RunEvent {
  ts: number;
  type: string; // "status" | "node" | "done" | "error" | "eof"
  detail?: string;
  node?: string;
  label?: string;
  action_plan?: string[];
  files_changed?: string[];
  test_passed?: boolean;
  test_output?: string;
  pr_url?: string;
  total_tokens?: number;
  cost_usd?: number;
  elapsed_seconds?: number;
  error?: string;
  status?: string;
  [key: string]: unknown;
}

export interface RunSummary {
  id: string;
  mode: "issue" | "task";
  target: string;
  status: "queued" | "running" | "done" | "failed";
  created_at: string;
  result: Record<string, unknown>;
}

export interface SolveRequest {
  issue_url?: string;
  repo_path?: string;
  task?: string;
  dry_run?: boolean;
  no_pr?: boolean;
}

export async function startSolve(req: SolveRequest) {
  return fetchJSON<{ run_id: string; status: string; mode: string }>(
    "/solve",
    { method: "POST", body: JSON.stringify(req) }
  );
}

export async function getRuns() {
  return fetchJSON<{ runs: RunSummary[] }>("/runs");
}

export async function getRun(runId: string) {
  return fetchJSON<RunSummary & { events: RunEvent[] }>(`/runs/${encodeURIComponent(runId)}`);
}

// ── Billing ───────────────────────────────────────────────────────────────

export interface BillingPlans {
  tiers: Record<string, { name: string; features: string[] }>;
  packages: Record<string, {
    name: string;
    days: number;
    prices: Record<string, number>;   // smallest unit: paise / cents
    display: Record<string, string>;
  }>;
  currencies: string[];
  limits: Record<string, number>;
}

export interface BillingStatus {
  tier: "free" | "pro";
  expires_at?: string | null;
  package?: string | null;
  usage: { queries_today: number; runs_this_month: number };
  remaining?: { queries_today: number; runs_this_month: number };
}

export interface OrderResponse {
  order_id: string;
  amount: number;
  currency: string;
  package: string;
  key_id: string;
  name: string;
  description: string;
}

export async function getBillingPlans() {
  return fetchJSON<BillingPlans>("/billing/plans");
}

export async function getBillingStatus() {
  return fetchJSON<BillingStatus>("/billing/status", undefined, true);
}

export async function createOrder(pkg: string, currency: string) {
  return fetchJSON<OrderResponse>(
    "/billing/order",
    { method: "POST", body: JSON.stringify({ package: pkg, currency }) }
  );
}

export async function verifyPayment(params: {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
  package: string;
  currency: string;
}) {
  return fetchJSON<{ status: string; tier: string; expires_at: string }>(
    "/billing/verify",
    { method: "POST", body: JSON.stringify(params) }
  );
}

export function streamRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onDone: () => void,
  onError: (err: string) => void
): () => void {
  const auth = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  const es = new EventSource(`${BASE}/solve/${encodeURIComponent(runId)}/events${auth}`);

  es.onmessage = (e) => {
    if (e.data === "[DONE]") {
      es.close();
      onDone();
      return;
    }
    try {
      onEvent(JSON.parse(e.data) as RunEvent);
    } catch {
      // skip malformed frames
    }
  };

  es.onerror = () => {
    es.close();
    onError("Run event stream disconnected");
  };

  return () => es.close();
}
