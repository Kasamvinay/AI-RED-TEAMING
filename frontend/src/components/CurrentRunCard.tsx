// src/components/CurrentRunCard.tsx
import { motion } from "framer-motion";
import { ClockIcon } from "./icons";
import type { StatusResponse } from "../types";
import { useEffect, useState } from "react";

function useElapsed(startedAt?: string): string {
  const [elapsed, setElapsed] = useState("0s");

  useEffect(() => {
    if (!startedAt) return;
    const update = () => {
      const diff = Date.now() - new Date(startedAt).getTime();
      const s = Math.floor(diff / 1000);
      if (s < 60) setElapsed(`${s}s`);
      else if (s < 3600) setElapsed(`${Math.floor(s / 60)}m ${s % 60}s`);
      else setElapsed(`${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  return elapsed;
}

export function CurrentRunCard({ status }: { status: StatusResponse }) {
  const elapsed = useElapsed(status.started_at);
  const progress = status.max_iterations
    ? Math.round(((status.iteration ?? 0) / status.max_iterations) * 100)
    : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl2 border border-line bg-card p-6 shadow-card"
    >
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
        Current Assessment
      </h3>

      <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
        <div>
          <p className="text-xs text-muted">Objective</p>
          <p className="mt-0.5 font-semibold text-ink capitalize">
            {status.objective?.replace(/_/g, " ") ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Strategy</p>
          <p className="mt-0.5 font-semibold text-ink capitalize">
            {status.strategy?.replace(/_/g, " ") ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Current Stage</p>
          <p className="mt-0.5 font-semibold text-brand-600 capitalize">
            {status.stage?.replace(/_/g, " ") ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Progress</p>
          <p className="mt-0.5 font-semibold text-ink">
            {status.iteration ?? 0} / {status.max_iterations ?? 0}
          </p>
        </div>
        <div className="flex items-end gap-1.5">
          <ClockIcon className="h-4 w-4 text-muted" />
          <div>
            <p className="text-xs text-muted">Elapsed</p>
            <p className="mt-0.5 font-semibold text-ink tabular-nums">
              {status.state === "running" ? elapsed : "—"}
            </p>
          </div>
        </div>
        <div>
          <p className="text-xs text-muted">Status</p>
          <p className="mt-0.5 font-semibold capitalize text-ink">{status.state}</p>
        </div>
      </div>

      {/* progress bar */}
      <div className="mt-5">
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>Overall Progress</span>
          <span>{progress}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
          <motion.div
            className="h-full rounded-full bg-brand-500"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* current attack preview */}
      {status.current_attack_preview && (
        <div className="mt-4 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3">
          <p className="mb-1 text-xs font-medium text-brand-500">Current Attack Preview</p>
          <p className="text-sm text-ink line-clamp-2">
            {status.current_attack_preview}
          </p>
        </div>
      )}
    </motion.div>
  );
}
