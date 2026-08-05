// src/components/Header.tsx
import { StatusBadge } from "./StatusBadge";
import type { RunState } from "../types";

interface HeaderProps {
  state: RunState;
  onNav: (page: "dashboard" | "runs" | "report") => void;
  activePage: string;
}

const NAV = [
  { id: "dashboard", label: "Dashboard" },
  { id: "runs", label: "Previous Runs" },
  { id: "report", label: "Report Viewer" },
] as const;

export function Header({ state, onNav, activePage }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-card/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        {/* logo mark */}
        <button
          onClick={() => onNav("dashboard")}
          className="flex items-center gap-2.5 group"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500 shadow-sm group-hover:bg-brand-600 transition-colors">
            {/* small shield + lock — original logomark, not Salesforce's */}
            <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2.5 20 6v6c0 4.8-3.3 8-8 9.5C7.3 20 4 16.8 4 12V6Z" />
              <circle cx="12" cy="12" r="2.5" />
            </svg>
          </div>
          <div className="leading-none">
            <p className="text-sm font-bold text-ink">RedTeam Console</p>
            <p className="text-[11px] text-muted">Autonomous AI Security</p>
          </div>
        </button>

        {/* nav */}
        <nav className="flex gap-1">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => onNav(item.id as never)}
              className={[
                "rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                activePage === item.id
                  ? "bg-brand-50 text-brand-600"
                  : "text-muted hover:bg-surface hover:text-ink",
              ].join(" ")}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <StatusBadge status={state} />
      </div>
    </header>
  );
}
