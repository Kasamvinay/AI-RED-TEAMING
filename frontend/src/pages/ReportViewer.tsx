// src/pages/ReportViewer.tsx
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { RiskBadge } from "../components/RiskBadge";
import type { AttackHistoryItem, HistoryResponse } from "../types";
import { api } from "../lib/api";

interface ReportViewerProps {
  runId: string | null;
}

function OutcomePill({ outcome }: { outcome: AttackHistoryItem["outcome"] }) {
  const styles = {
    success: "bg-red-50 text-danger border-red-200",
    partial: "bg-amber-50 text-warning border-amber-200",
    failure: "bg-green-50 text-success border-green-200",
  };
  const labels = { success: "Injected", partial: "Partial", failure: "Blocked" };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${styles[outcome]}`}>
      {labels[outcome]}
    </span>
  );
}

export function ReportViewer({ runId }: ReportViewerProps) {
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    if (!runId) return;
    setHistory(null);
    setError(null);
    api.history(runId).then(setHistory).catch((e) => setError(e.message));
  }, [runId]);

  if (!runId) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16 text-center text-muted">
        Select a run from Previous Runs to view its attack history.
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-8 text-danger">
        {error}
      </div>
    );
  }

  if (!history) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16 text-center text-muted">
        Loading…
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="mx-auto max-w-6xl px-6 py-8"
    >
      {/* document header */}
      <div className="mb-6 rounded-xl2 border border-line bg-card p-6 shadow-card">
        <p className="text-xs text-muted uppercase tracking-widest mb-1">Attack History</p>
        <h2 className="text-2xl font-bold text-ink">Run #{runId}</h2>
        <p className="mt-1 text-sm text-muted">{history.count} attacks recorded</p>
      </div>

      {/* legend */}
      <div className="mb-4 flex gap-4 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-danger" />Injected (success)</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-warning" />Partial</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-success" />Blocked</span>
      </div>

      {/* attack rows */}
      <div className="space-y-2">
        {history.attacks.map((attack, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            className="rounded-xl border border-line bg-card shadow-card overflow-hidden"
          >
            {/* collapsed header — always visible */}
            <button
              className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-surface transition-colors"
              onClick={() => setExpanded(expanded === i ? null : i)}
            >
              <span className="w-8 flex-shrink-0 text-center text-sm font-semibold tabular-nums text-muted">
                {attack.iteration}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink capitalize">
                  {attack.strategy.replace(/_/g, " ")}
                </p>
                <p className="text-xs text-muted truncate">{attack.prompt.slice(0, 90)}…</p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                <OutcomePill outcome={attack.outcome} />
                <RiskBadge severity={attack.severity} />
                <span className="text-xs tabular-nums text-muted">
                  r={attack.reward.toFixed(2)}
                </span>
                <span className="text-muted text-xs">{expanded === i ? "▲" : "▼"}</span>
              </div>
            </button>

            {/* expanded detail */}
            {expanded === i && (
              <div className="border-t border-line px-5 py-4 space-y-4 bg-surface">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 text-sm">
                  <div>
                    <p className="text-xs text-muted">Strategy</p>
                    <p className="mt-0.5 capitalize">{attack.strategy.replace(/_/g, " ")}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted">Score</p>
                    <p className="mt-0.5">{attack.score.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted">Confidence</p>
                    <p className="mt-0.5">{(attack.confidence * 100).toFixed(0)}%</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted mb-1">Judge Analysis</p>
                  <p className="text-sm text-ink">{attack.explanation}</p>
                </div>

                {attack.recommendation && (
                  <div>
                    <p className="text-xs text-muted mb-1">Recommendation</p>
                    <p className="text-sm text-ink">{attack.recommendation}</p>
                  </div>
                )}

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium text-muted mb-2">Attack Prompt</p>
                    <pre className="whitespace-pre-wrap rounded-xl bg-surface border border-line px-4 py-3 text-xs text-ink font-mono leading-relaxed max-h-48 overflow-y-auto">
                      {attack.prompt}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted mb-2">Target Response</p>
                    <pre className="whitespace-pre-wrap rounded-xl bg-surface border border-line px-4 py-3 text-xs text-ink font-mono leading-relaxed max-h-48 overflow-y-auto">
                      {attack.response || "(no response)"}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
