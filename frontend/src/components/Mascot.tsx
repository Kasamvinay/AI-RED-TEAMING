// src/components/Mascot.tsx
//
// An original "cloud assistant" mascot — round, soft, no ears/hood/tail,
// nothing that echoes Salesforce's Astro character. Built as an animated
// SVG driven by Framer Motion so it works out of the box with zero extra
// assets. If you later create a real .riv file in the Rive editor (state
// machine with states: Idle, Thinking, Typing, Talking, Inspecting,
// Running, Celebrating, and a string input "stage" to drive transitions),
// pass `riveSrc` and this component swaps to <RiveMascot> automatically —
// nothing else in the app needs to change.

import { motion, type Variants } from "framer-motion";
import { RiveMascot } from "./RiveMascot";
import type { PipelineStage } from "../types";

export type MascotPose =
  | "idle"
  | "thinking"
  | "typing"
  | "talking"
  | "inspecting"
  | "running"
  | "celebrating";

const STAGE_TO_POSE: Record<NonNullable<PipelineStage>, MascotPose> = {
  strategy_selected: "thinking",
  prompt_generated: "typing",
  attack_sent: "running",
  response_received: "talking",
  judge_completed: "inspecting",
  knowledge_updated: "celebrating",
  report_generated: "celebrating",
  completed: "celebrating",
};

export function poseForStage(stage: PipelineStage): MascotPose {
  if (!stage) return "idle";
  return STAGE_TO_POSE[stage] ?? "idle";
}

interface MascotProps {
  pose: MascotPose;
  /** Horizontal position as a percentage (0-100) of the pipeline track width. */
  xPercent: number;
  riveSrc?: string;
  size?: number;
}

export function Mascot({ pose, xPercent, riveSrc, size = 64 }: MascotProps) {
  if (riveSrc) {
    return <RiveMascot src={riveSrc} pose={pose} xPercent={xPercent} size={size} />;
  }
  return <SvgMascot pose={pose} xPercent={xPercent} size={size} />;
}

const bodyVariants: Variants = {
  idle: { y: [0, -4, 0], rotate: 0, transition: { duration: 2.4, repeat: Infinity, ease: "easeInOut" } },
  thinking: { y: [0, -3, 0], rotate: [-4, 4, -4], transition: { duration: 1.8, repeat: Infinity, ease: "easeInOut" } },
  typing: { y: [0, -2, 0], rotate: 0, transition: { duration: 0.5, repeat: Infinity, ease: "easeInOut" } },
  talking: { y: [0, -3, 0], rotate: [0, 2, -2, 0], transition: { duration: 0.9, repeat: Infinity, ease: "easeInOut" } },
  inspecting: { y: [0, -3, 0], rotate: -6, transition: { duration: 1.6, repeat: Infinity, ease: "easeInOut" } },
  running: { y: [0, -6, 0], rotate: 0, transition: { duration: 0.4, repeat: Infinity, ease: "easeInOut" } },
  celebrating: { y: [0, -10, 0], rotate: [-8, 8, -8], transition: { duration: 0.6, repeat: Infinity, ease: "easeInOut" } },
};

function SvgMascot({ pose, xPercent, size }: { pose: MascotPose; xPercent: number; size: number }) {
  return (
    <motion.div
      className="absolute top-0 pointer-events-none select-none"
      style={{ width: size, height: size, marginLeft: -size / 2 }}
      animate={{ left: `${xPercent}%` }}
      transition={{ type: "spring", stiffness: 120, damping: 16 }}
    >
      <motion.svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        variants={bodyVariants}
        animate={pose}
      >
        {/* soft ground shadow */}
        <ellipse cx="50" cy="92" rx="22" ry="4" fill="#0176D3" opacity="0.08" />

        {/* body — a single rounded cloud/blob shape, no ears/hood/tail */}
        <path
          d="M50 22c12 0 20 8 21.5 17.5 8 1.5 13.5 8 13.5 15.5 0 9-8 16-18 16H33c-10 0-18-7-18-16 0-7.5 5.5-14 13.5-15.5C30 30 38 22 50 22Z"
          fill="#EAF4FD"
          stroke="#0176D3"
          strokeWidth="2"
        />

        {/* eyes */}
        <motion.g
          animate={
            pose === "inspecting"
              ? { scaleY: [1, 0.15, 1] }
              : pose === "idle"
              ? { scaleY: [1, 1, 0.15, 1, 1] }
              : { scaleY: 1 }
          }
          transition={{ duration: pose === "idle" ? 3.2 : 1.4, repeat: Infinity, times: pose === "idle" ? [0, 0.85, 0.92, 0.98, 1] : undefined }}
          style={{ transformOrigin: "50px 55px" }}
        >
          <circle cx="42" cy="55" r="3.4" fill="#1B2631" />
          <circle cx="58" cy="55" r="3.4" fill="#1B2631" />
        </motion.g>

        {/* blush */}
        <circle cx="34" cy="62" r="4" fill="#0176D3" opacity="0.14" />
        <circle cx="66" cy="62" r="4" fill="#0176D3" opacity="0.14" />

        {/* mouth — shape depends on pose */}
        {pose === "talking" ? (
          <motion.ellipse
            cx="50" cy="66" rx="4" ry="3" fill="#1B2631"
            animate={{ ry: [3, 5.5, 2, 4, 3] }}
            transition={{ duration: 0.6, repeat: Infinity }}
          />
        ) : pose === "celebrating" ? (
          <path d="M42 64c2.5 4 13 4 16 0" stroke="#1B2631" strokeWidth="2.4" fill="none" strokeLinecap="round" />
        ) : (
          <path d="M44 66c2 2 10 2 12 0" stroke="#1B2631" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        )}

        {/* left arm */}
        <motion.path
          d="M28 66c-4 2-7 5-8 9"
          stroke="#0176D3" strokeWidth="3" fill="none" strokeLinecap="round"
          animate={
            pose === "celebrating"
              ? { d: ["M28 66c-4 2-7 5-8 9", "M28 66c-6 -2 -9 -3 -11 -1", "M28 66c-4 2-7 5-8 9"] }
              : pose === "typing"
              ? { d: ["M28 66c-2 4-3 7-2 10", "M28 66c-4 3-5 6-3 9", "M28 66c-2 4-3 7-2 10"] }
              : {}
          }
          transition={{ duration: 0.4, repeat: pose === "celebrating" || pose === "typing" ? Infinity : 0 }}
        />
        {/* right arm */}
        <motion.path
          d="M72 66c4 2 7 5 8 9"
          stroke="#0176D3" strokeWidth="3" fill="none" strokeLinecap="round"
          animate={
            pose === "celebrating"
              ? { d: ["M72 66c4 2 7 5 8 9", "M72 66c6 -2 9 -3 11 -1", "M72 66c4 2 7 5 8 9"] }
              : pose === "typing"
              ? { d: ["M72 66c2 4 3 7 2 10", "M72 66c4 3 5 6 3 9", "M72 66c2 4 3 7 2 10"] }
              : {}
          }
          transition={{ duration: 0.4, repeat: pose === "celebrating" || pose === "typing" ? Infinity : 0, delay: 0.15 }}
        />

        {/* thinking dots */}
        {pose === "thinking" && (
          <motion.g animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 1.4, repeat: Infinity }}>
            <circle cx="76" cy="24" r="2" fill="#0176D3" />
            <circle cx="82" cy="18" r="2.6" fill="#0176D3" />
            <circle cx="90" cy="12" r="3.2" fill="#0176D3" />
          </motion.g>
        )}

        {/* motion lines while "running" */}
        {pose === "running" && (
          <motion.g
            stroke="#0176D3" strokeWidth="2" strokeLinecap="round" opacity="0.5"
            animate={{ opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 0.4, repeat: Infinity }}
          >
            <path d="M10 50h8" />
            <path d="M8 60h8" />
            <path d="M12 70h8" />
          </motion.g>
        )}

        {/* sparkle burst while celebrating */}
        {pose === "celebrating" && (
          <motion.g
            animate={{ opacity: [0, 1, 0], scale: [0.6, 1.2, 0.6] }}
            transition={{ duration: 0.9, repeat: Infinity }}
          >
            <path d="M18 30l1.6 3.6L23 35l-3.4 1.4L18 40l-1.6-3.6L13 35l3.4-1.4Z" fill="#0176D3" />
            <path d="M84 34l1.2 2.6L88 38l-2.8 1.1L84 42l-1.2-2.9L80 38l2.8-1.4Z" fill="#0176D3" />
          </motion.g>
        )}
      </motion.svg>
    </motion.div>
  );
}
