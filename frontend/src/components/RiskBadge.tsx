// src/components/RiskBadge.tsx
import type { Severity } from "../types";

const STYLES: Record<Severity, string> = {
  critical: "bg-red-50 text-critical border-red-200",
  high: "bg-red-50 text-danger border-red-200",
  medium: "bg-amber-50 text-warning border-amber-200",
  low: "bg-blue-50 text-brand-600 border-blue-200",
  info: "bg-gray-50 text-muted border-line",
  none: "bg-green-50 text-success border-green-200",
};

const LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
  none: "Minimal",
};

export function RiskBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${STYLES[severity]}`}
    >
      {LABELS[severity]}
    </span>
  );
}
