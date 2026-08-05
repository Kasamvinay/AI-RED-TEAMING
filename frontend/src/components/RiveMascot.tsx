// src/components/RiveMascot.tsx
//
// Real Rive integration, used automatically by <Mascot> once you pass a
// `riveSrc`. NOT required for the app to run — the SVG mascot in
// Mascot.tsx is the default and needs no external asset.
//
// To use this for real:
//   1. Design the character in the Rive editor (https://rive.app) with a
//      state machine (suggested name: "MascotStateMachine") containing
//      seven states — Idle, Thinking, Typing, Talking, Inspecting,
//      Running, Celebrating — and a single string input, e.g. "pose",
//      that drives which state is active.
//   2. Export the .riv file into src/assets/mascot.riv.
//   3. Pass riveSrc="/src/assets/mascot.riv" to <Mascot>.
//
// This component pushes the current `pose` into that state machine's
// "pose" input on every change; positioning/movement between pipeline
// stages is still handled by the same Framer Motion wrapper the SVG
// mascot uses, so both versions move identically — only the character
// rendering differs.

import { useEffect } from "react";
import { useRive, useStateMachineInput } from "@rive-app/react-canvas";
import { motion } from "framer-motion";
import type { MascotPose } from "./Mascot";

const STATE_MACHINE_NAME = "MascotStateMachine";
const POSE_INPUT_NAME = "pose";

interface RiveMascotProps {
  src: string;
  pose: MascotPose;
  xPercent: number;
  size: number;
}

export function RiveMascot({ src, pose, xPercent, size }: RiveMascotProps) {
  const { RiveComponent, rive } = useRive({
    src,
    stateMachines: STATE_MACHINE_NAME,
    autoplay: true,
  });

  const poseInput = useStateMachineInput(rive, STATE_MACHINE_NAME, POSE_INPUT_NAME);

  useEffect(() => {
    if (poseInput) {
      poseInput.value = pose as unknown as number;
    }
  }, [poseInput, pose]);

  return (
    <motion.div
      className="absolute top-0 pointer-events-none select-none"
      style={{ width: size, height: size, marginLeft: -size / 2 }}
      animate={{ left: `${xPercent}%` }}
      transition={{ type: "spring", stiffness: 120, damping: 16 }}
    >
      <RiveComponent style={{ width: size, height: size }} />
    </motion.div>
  );
}
