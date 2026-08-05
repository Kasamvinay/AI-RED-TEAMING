// src/components/RunLauncher.tsx
import { useState } from "react";
import { api } from "../lib/api";
import type { StartRunRequest } from "../types";

interface RunLauncherProps {
  objectives: string[];
  isRunning: boolean;
}

export function RunLauncher({ objectives, isRunning }: RunLauncherProps) {
  const [form, setForm] = useState<StartRunRequest>({
    objective: "customer_support",
    target: "mock",
    prompt_generator: "template",
    max_iterations: 15,
    max_llm_calls: 0,
    run_name: "prompt_injection_run",
    fresh_kb: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setError(null);
    setStarting(true);
    try {
      await api.startRun({
        ...form,
        max_iterations: Number(form.max_iterations),
        max_llm_calls: Number(form.max_llm_calls),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  };

  const field = "rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100";

  return (
    <div className="rounded-xl2 border border-line bg-card p-6 shadow-card">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
        Configure Run
      </h3>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Objective</label>
          <select
            className={field}
            value={form.objective}
            onChange={(e) => setForm({ ...form, objective: e.target.value })}
          >
            {objectives.map((o) => (
              <option key={o} value={o}>
                {o.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Target</label>
          <select
            className={field}
            value={form.target}
            onChange={(e) => setForm({ ...form, target: e.target.value })}
          >
            <option value="mock">mock (offline demo)</option>
            <option value="acme_supportbot">acme_supportbot</option>
            <option value="openai">openai</option>
            <option value="rest_api">rest_api</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Generator</label>
          <select
            className={field}
            value={form.prompt_generator}
            onChange={(e) =>
              setForm({
                ...form,
                prompt_generator: e.target.value as "template" | "llm",
              })
            }
          >
            <option value="template">template ($0)</option>
            <option value="llm">llm (API)</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted">Iterations</label>
          <input
            type="number"
            min={1}
            max={200}
            className={field}
            value={form.max_iterations}
            onChange={(e) =>
              setForm({ ...form, max_iterations: Number(e.target.value) })
            }
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-line accent-brand-500"
            checked={form.fresh_kb}
            onChange={(e) => setForm({ ...form, fresh_kb: e.target.checked })}
          />
          Fresh knowledge base
        </label>

        <button
          onClick={handleStart}
          disabled={isRunning || starting}
          className={[
            "rounded-xl px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all",
            isRunning || starting
              ? "cursor-not-allowed bg-muted"
              : "bg-brand-500 hover:bg-brand-600 active:scale-95",
          ].join(" ")}
        >
          {isRunning ? "Run in progress…" : starting ? "Starting…" : "Start Attack Run"}
        </button>
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
