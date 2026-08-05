// src/lib/api.ts
import type {
  HistoryResponse,
  ReportSummary,
  RunRecord,
  StartRunRequest,
  StatusResponse,
} from "../types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.error ?? res.statusText);
  }
  return body as T;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  objectives: () => get<{ objectives: string[] }>("/objectives"),
  status: () => get<StatusResponse>("/status"),
  runs: () => get<{ runs: RunRecord[] }>("/runs"),
  reports: () => get<{ reports: ReportSummary[] }>("/reports"),
  history: (runId: string) => get<HistoryResponse>(`/history/${runId}`),
  startRun: (payload: StartRunRequest) =>
    post<{ run_id: string; run_name: string; status: string }>("/runs", payload),
  mitigationUrl: (runId: string) => `${BASE}/mitigation/${runId}`,
  technicalUrl: (runId: string, fmt: "md" | "json") => `${BASE}/reports/${runId}/technical/${fmt}`,
};
