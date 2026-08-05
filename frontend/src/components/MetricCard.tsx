// src/components/MetricCard.tsx
import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  accent?: "brand" | "success" | "warning" | "danger";
  icon?: ReactNode;
}

const ACCENT_TEXT: Record<string, string> = {
  brand: "text-brand-600",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

export function MetricCard({ label, value, accent = "brand", icon }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl2 border border-line bg-card p-5 shadow-card"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted">{label}</span>
        {icon && <span className={`${ACCENT_TEXT[accent]} opacity-70`}>{icon}</span>}
      </div>
      <div className={`mt-2 text-3xl font-semibold ${ACCENT_TEXT[accent]}`}>{value}</div>
    </motion.div>
  );
}
