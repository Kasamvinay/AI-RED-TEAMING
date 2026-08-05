// src/components/Pipeline.tsx
import { motion } from "framer-motion";
import type { PipelineStage } from "../types";
import {
  StrategyIcon,
  GeneratorIcon,
  ChatbotIcon,
  JudgeIcon,
  KnowledgeBaseIcon,
} from "./icons";
import { Mascot, poseForStage } from "./Mascot";

const STAGES: Array<{
  key: PipelineStage;
  label: string;
  sub: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}> = [
  {
    key: "strategy_selected",
    label: "Strategy Planner",
    sub: "Selects attack strategy",
    Icon: StrategyIcon,
  },
  {
    key: "prompt_generated",
    label: "Prompt Generator",
    sub: "Crafts the attack prompt",
    Icon: GeneratorIcon,
  },
  {
    key: "attack_sent",
    label: "Target Chatbot",
    sub: "Attack is executed",
    Icon: ChatbotIcon,
  },
  {
    key: "judge_completed",
    label: "Judge LLM",
    sub: "Evaluates the response",
    Icon: JudgeIcon,
  },
  {
    key: "knowledge_updated",
    label: "Knowledge Base",
    sub: "Stores & learns",
    Icon: KnowledgeBaseIcon,
  },
];

// Map each stage key to a 0-100% x position for the mascot
const STAGE_X_PERCENT: Partial<Record<NonNullable<PipelineStage>, number>> = {
  strategy_selected: 10,
  prompt_generated: 30,
  attack_sent: 50,
  response_received: 50, // mascot stays at chatbot while receiving
  judge_completed: 70,
  knowledge_updated: 90,
  report_generated: 90,
  completed: 90,
};

interface PipelineProps {
  currentStage: PipelineStage;
  checklist: Record<string, boolean>;
}

export function Pipeline({ currentStage, checklist }: PipelineProps) {
  const pose = poseForStage(currentStage);
  const xPercent = currentStage ? (STAGE_X_PERCENT[currentStage] ?? 10) : 10;

  return (
    <div className="rounded-xl2 border border-line bg-card p-8 shadow-card">
      {/* mascot track — sits above the nodes, mascot slides between them */}
      <div className="relative h-20 mb-6">
        <Mascot pose={pose} xPercent={xPercent} size={72} />
      </div>

      {/* connector line behind the nodes */}
      <div className="relative flex items-center justify-between">
        <div className="absolute inset-y-[2.1rem] left-6 right-6 h-px bg-line" />

        {STAGES.map((stage, i) => {
          const isDone = !!checklist[stage.key ?? ""];
          const isActive = currentStage === stage.key ||
            (stage.key === "attack_sent" && currentStage === "response_received");

          return (
            <div key={stage.key} className="relative z-10 flex flex-col items-center gap-3 flex-1">
              {/* node circle */}
              <motion.div
                animate={
                  isActive
                    ? { scale: [1, 1.08, 1] }
                    : { scale: 1 }
                }
                transition={{ duration: 1.6, repeat: isActive ? Infinity : 0, ease: "easeInOut" }}
                className={[
                  "flex h-16 w-16 items-center justify-center rounded-full border-2 transition-all duration-500",
                  isActive
                    ? "border-brand-500 bg-brand-50 text-brand-600 shadow-glow animate-soft-pulse"
                    : isDone
                    ? "border-green-400 bg-green-50 text-success"
                    : "border-line bg-surface text-muted",
                ].join(" ")}
              >
                <stage.Icon className="h-7 w-7" />
              </motion.div>

              {/* labels */}
              <div className="text-center">
                <p
                  className={[
                    "text-sm font-semibold leading-tight",
                    isActive ? "text-brand-600" : isDone ? "text-ink" : "text-muted",
                  ].join(" ")}
                >
                  {stage.label}
                </p>
                <p className="mt-0.5 text-xs text-muted">{stage.sub}</p>
              </div>

              {/* done tick */}
              {isDone && (
                <motion.span
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-success text-white text-[10px] font-bold"
                >
                  ✓
                </motion.span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
