// src/components/StatusBadge.tsx
import type { RunState, RunStatus } from "../types";

const STYLES: Record<string, string> = {
  running: "bg-brand-50 text-brand-600 border-brand-200",
  completed: "bg-green-50 text-success border-green-200",
  failed: "bg-red-50 text-danger border-red-200",
  idle: "bg-gray-50 text-muted border-line",
};

const LABELS: Record<string, string> = {
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  idle: "Idle",
};

export function StatusBadge({ status }: { status: RunState | RunStatus }) {
  const style = STYLES[status] ?? STYLES.idle;
  const label = LABELS[status] ?? status;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${style}`}
    >
      {status === "running" && (
        <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
      )}
      {label}
    </span>
  );
}
