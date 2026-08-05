// src/pages/Dashboard.tsx
import { motion } from "framer-motion";
import { RiskBadge } from "../components/RiskBadge";
import { MetricCard } from "../components/MetricCard";
import { Pipeline } from "../components/Pipeline";
import { CurrentRunCard } from "../components/CurrentRunCard";
import { RunLauncher } from "../components/RunLauncher";
import { OwaspBadgeIcon, DownloadIcon } from "../components/icons";
import type { RunRecord, StatusResponse } from "../types";
import { api } from "../lib/api";

const EMPTY_CHECKLIST = {
  strategy_selected: false,
  prompt_generated: false,
  attack_sent: false,
  response_received: false,
  judge_completed: false,
  knowledge_updated: false,
};

interface DashboardProps {
  status: StatusResponse;
  objectives: string[];
  latestRun: RunRecord | null;
}

export function Dashboard({ status, objectives, latestRun }: DashboardProps) {
  const isRunning = status.state === "running";
  const checklist = status.stage_checklist ?? EMPTY_CHECKLIST;

  // Derive quick-metric values — prefer live status if running, else latest run
  const totalAttacks = isRunning
    ? (status.iteration ?? 0)
    : (latestRun?.total_attacks ?? 0);
  const successfulAttacks = isRunning
    ? 0 // not tracked live; shown post-run from latestRun
    : (latestRun?.successful_attacks ?? 0);
  const highestSeverity = latestRun?.highest_severity ?? "none";

  // Simple 0-100 score: 100 - penalty per severity finding
  const score = latestRun
    ? Math.max(
        0,
        100 -
          (latestRun.successful_attacks ?? 0) * 15 -
          (latestRun.partial_attacks ?? 0) * 5
      )
    : 100;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-6xl space-y-6 px-6 py-8"
    >
      {/* OWASP header band */}
      <div className="flex items-center gap-4 rounded-xl2 border border-brand-100 bg-brand-50 px-6 py-4">
        <OwaspBadgeIcon className="h-9 w-9 flex-shrink-0 text-brand-500" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-widest text-brand-400">
            OWASP LLM01
          </p>
          <p className="text-lg font-bold text-brand-700">Prompt Injection</p>
          <p className="text-sm text-muted">
            Autonomously testing enterprise AI chatbot security
          </p>
        </div>
        {latestRun && (
          <div className="ml-auto">
            <RiskBadge severity={highestSeverity} />
          </div>
        )}
      </div>

      {/* launch controls */}
      <RunLauncher objectives={objectives} isRunning={isRunning} />

      {/* pipeline — the centrepiece */}
      <Pipeline currentStage={status.stage ?? null} checklist={checklist} />

      {/* current run summary */}
      <CurrentRunCard status={status} />

      {/* quick metrics — 4 cards max */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard label="Attacks Executed" value={totalAttacks} accent="brand" />
        <MetricCard
          label="Successful Attacks"
          value={successfulAttacks}
          accent={successfulAttacks > 0 ? "danger" : "success"}
        />
        <MetricCard
          label="Risk Level"
          value={
            <RiskBadge severity={highestSeverity} />
          }
          accent={
            highestSeverity === "critical" || highestSeverity === "high"
              ? "danger"
              : highestSeverity === "medium"
              ? "warning"
              : "success"
          }
        />
        <MetricCard
          label="Security Score"
          value={`${score}`}
          accent={score < 60 ? "danger" : score < 80 ? "warning" : "success"}
        />
      </div>

      {/* reports */}
      {latestRun?.status === "completed" && (
        <div className="rounded-xl2 border border-line bg-card p-6 shadow-card">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
            Reports
          </h3>
          <div className="flex flex-wrap gap-3">
            {latestRun.technical_report_md && (
              <a
                href={api.technicalUrl(latestRun.run_id, "md")}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink shadow-card hover:shadow-cardHover hover:border-brand-200 transition-all"
              >
                <DownloadIcon className="h-4 w-4 text-brand-500" />
                Technical Report
              </a>
            )}
            {latestRun.mitigation_report_pdf && (
              <a
                href={api.mitigationUrl(latestRun.run_id)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-600 transition-colors"
              >
                <DownloadIcon className="h-4 w-4" />
                Executive Mitigation Report
              </a>
            )}
          </div>
        </div>
      )}

      {/* failed run error */}
      {status.state === "failed" && (
        <div className="rounded-xl2 border border-red-200 bg-red-50 px-6 py-4 text-sm text-danger">
          <strong>Run failed:</strong> {status.error}
        </div>
      )}
    </motion.div>
  );
}
