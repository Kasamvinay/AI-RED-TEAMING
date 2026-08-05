// src/types.ts
// Mirrors the JSON shapes returned by the existing Flask API (api/app.py).
// Nothing here invents new backend behavior — it's a typed view of what
// GET /api/status, /api/runs, /api/reports, /api/history/<id> already return.

export type PipelineStage =
  | "strategy_selected"
  | "prompt_generated"
  | "attack_sent"
  | "response_received"
  | "judge_completed"
  | "knowledge_updated"
  | "report_generated"
  | "completed"
  | null;

export type RunState = "idle" | "running" | "completed" | "failed";

export interface StageChecklist {
  strategy_selected: boolean;
  prompt_generated: boolean;
  attack_sent: boolean;
  response_received: boolean;
  judge_completed: boolean;
  knowledge_updated: boolean;
}

export interface StatusResponse {
  state: RunState;
  run_id?: string;
  run_name?: string;
  objective?: string;
  target?: string;
  iteration?: number;
  max_iterations?: number;
  stage?: PipelineStage;
  strategy?: string | null;
  current_attack_preview?: string | null;
  stage_checklist?: StageChecklist;
  started_at?: string;
  error?: string;
}

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "none";
export type RunStatus = "running" | "completed" | "failed";

export interface RunRecord {
  run_id: string;
  run_name: string;
  objective: string;
  target_adapter: string;
  status: RunStatus;
  started_at: string;
  completed_at: string | null;
  max_iterations: number;
  total_attacks: number;
  successful_attacks: number;
  partial_attacks: number;
  highest_severity: Severity;
  technical_report_md: string | null;
  technical_report_json: string | null;
  mitigation_report_pdf: string | null;
  error: string | null;
}

export interface ReportSummary {
  run_id: string;
  run_name: string;
  completed_at: string | null;
  highest_severity: Severity;
  total_attacks: number;
  successful_attacks: number;
  has_mitigation_pdf: boolean;
  has_technical_report: boolean;
}

export interface AttackHistoryItem {
  iteration: number;
  strategy: string;
  technique: string;
  source: string;
  outcome: "success" | "partial" | "failure";
  severity: Severity;
  score: number;
  confidence: number;
  reward: number;
  explanation: string;
  recommendation: string;
  prompt: string;
  response: string;
  timestamp: string;
}

export interface HistoryResponse {
  run_id: string;
  count: number;
  attacks: AttackHistoryItem[];
}

export interface StartRunRequest {
  objective?: string;
  target?: string;
  prompt_generator?: "template" | "llm";
  max_iterations?: number;
  max_llm_calls?: number;
  run_name?: string;
  fresh_kb?: boolean;
}
