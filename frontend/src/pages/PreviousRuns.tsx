// src/pages/PreviousRuns.tsx
import { motion } from "framer-motion";
import { StatusBadge } from "../components/StatusBadge";
import { RiskBadge } from "../components/RiskBadge";
import { DownloadIcon } from "../components/icons";
import type { RunRecord } from "../types";
import { api } from "../lib/api";

interface PreviousRunsProps {
  runs: RunRecord[];
  onViewHistory: (runId: string) => void;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function PreviousRuns({ runs, onViewHistory }: PreviousRunsProps) {
  if (runs.length === 0) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16 text-center">
        <p className="text-muted">No runs yet — start one from the Dashboard.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-6xl space-y-4 px-6 py-8"
    >
      <h2 className="text-xl font-bold text-ink">Previous Runs</h2>

      {runs.map((run, i) => (
        <motion.div
          key={run.run_id}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06 }}
          className="rounded-xl2 border border-line bg-card p-5 shadow-card"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="font-semibold text-ink">{run.run_name}</p>
                <StatusBadge status={run.status} />
                <RiskBadge severity={run.highest_severity} />
              </div>
              <p className="mt-1 text-xs text-muted">
                #{run.run_id} · {run.objective.replace(/_/g, " ")} ·{" "}
                {run.started_at ? formatDate(run.started_at) : "—"}
              </p>
              {run.status === "completed" && (
                <p className="mt-1 text-xs text-muted">
                  {run.total_attacks} attacks · {run.successful_attacks} successful
                </p>
              )}
              {run.status === "failed" && run.error && (
                <p className="mt-1 text-xs text-danger">{run.error}</p>
              )}
            </div>

            {run.status === "completed" && (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => onViewHistory(run.run_id)}
                  className="rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink hover:border-brand-200 hover:text-brand-600 transition-colors"
                >
                  View History
                </button>
                {run.technical_report_md && (
                  <a
                    href={api.technicalUrl(run.run_id, "md")}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-xs font-medium text-ink hover:border-brand-200 hover:text-brand-600 transition-colors"
                  >
                    <DownloadIcon className="h-3.5 w-3.5" />
                    Technical
                  </a>
                )}
                {run.mitigation_report_pdf && (
                  <a
                    href={api.mitigationUrl(run.run_id)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-600 transition-colors"
                  >
                    <DownloadIcon className="h-3.5 w-3.5" />
                    Mitigation PDF
                  </a>
                )}
              </div>
            )}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
