// src/App.tsx
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Header } from "./components/Header";
import { Dashboard } from "./pages/Dashboard";
import { PreviousRuns } from "./pages/PreviousRuns";
import { ReportViewer } from "./pages/ReportViewer";
import type { RunRecord, RunState, StatusResponse } from "./types";
import { api } from "./lib/api";

const IDLE_STATUS: StatusResponse = { state: "idle" };

export default function App() {
  const [page, setPage] = useState<"dashboard" | "runs" | "report">("dashboard");
  const [status, setStatus] = useState<StatusResponse>(IDLE_STATUS);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [objectives, setObjectives] = useState<string[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // boot — load objectives + runs once
  useEffect(() => {
    api.objectives().then((d) => setObjectives(d.objectives)).catch(() => {});
    api.runs().then((d) => setRuns(d.runs)).catch(() => {});
  }, []);

  // poll status at 1.5s; refresh run list after a run completes
  useEffect(() => {
    let prevState: RunState = status.state;

    const poll = async () => {
      try {
        const s = await api.status();
        setStatus(s);
        if (prevState === "running" && s.state !== "running") {
          // run just finished — refresh the run list
          api.runs().then((d) => setRuns(d.runs)).catch(() => {});
        }
        prevState = s.state;
      } catch {
        // backend not reachable — keep showing last known status silently
      }
    };

    poll();
    const id = setInterval(poll, 1500);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const latestRun = runs.find((r: RunRecord) => r.status === "completed") ?? null;

  const handleViewHistory = (runId: string) => {
    setSelectedRunId(runId);
    setPage("report");
  };

  const pageTransition = {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -12 },
    transition: { duration: 0.22 },
  };

  return (
    <div className="min-h-screen bg-surface">
      <Header state={status.state} onNav={setPage} activePage={page} />

      <AnimatePresence mode="wait">
        {page === "dashboard" && (
          <motion.div key="dashboard" {...pageTransition}>
            <Dashboard
              status={status}
              objectives={objectives}
              latestRun={latestRun}
            />
          </motion.div>
        )}

        {page === "runs" && (
          <motion.div key="runs" {...pageTransition}>
            <PreviousRuns runs={runs} onViewHistory={handleViewHistory} />
          </motion.div>
        )}

        {page === "report" && (
          <motion.div key="report" {...pageTransition}>
            <ReportViewer runId={selectedRunId} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
