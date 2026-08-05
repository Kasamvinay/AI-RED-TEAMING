// src/components/icons.tsx
// Custom, minimal line-art icons for the five pipeline stages plus a few
// badges. Deliberately simple geometric shapes (not stock icon-pack
// glyphs) so they read as "designed for this product" rather than
// generic. Each accepts a `className` for sizing/coloring via Tailwind.

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

export function StrategyIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3.5v2.4M12 18.1v2.4M3.5 12h2.4M18.1 12h2.4" />
    </svg>
  );
}

export function GeneratorIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3.5" y="4.5" width="17" height="14" rx="2.5" />
      <path d="M7.5 9.5h5M7.5 13h8" />
      <path d="M16.2 12.4l1.6 1.6-1.6 1.6" />
    </svg>
  );
}

export function ChatbotIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="4" y="5.5" width="16" height="10.5" rx="3" />
      <path d="M9 20l2.2-3.5h1.6L15 20" />
      <circle cx="9" cy="10.7" r="1" fill="currentColor" stroke="none" />
      <circle cx="15" cy="10.7" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function JudgeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.5v17" />
      <path d="M5 8l-2.5 5a3.2 3.2 0 0 0 5 0L5 8Z" />
      <path d="M19 8l-2.5 5a3.2 3.2 0 0 0 5 0L19 8Z" />
      <path d="M4.7 8h6.6M12.7 8h6.6" />
      <path d="M8 20.5h8" />
    </svg>
  );
}

export function KnowledgeBaseIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M4 6.2c0-1.2 3.6-2.2 8-2.2s8 1 8 2.2v11.6c0 1.2-3.6 2.2-8 2.2s-8-1-8-2.2Z" />
      <path d="M4 6.2c0 1.2 3.6 2.2 8 2.2s8-1 8-2.2" />
      <path d="M4 12c0 1.2 3.6 2.2 8 2.2s8-1 8-2.2" />
    </svg>
  );
}

export function ReportIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M7 3.5h7l4 4v13H7Z" />
      <path d="M14 3.5v4h4" />
      <path d="M9.5 13h5M9.5 16h5M9.5 10h2.5" />
    </svg>
  );
}

export function OwaspBadgeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2.6 20 6v6c0 5-3.4 8.4-8 9.4C7.4 20.4 4 17 4 12V6Z" />
      <path d="M9 12.2l2 2 4-4.4" />
    </svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.5v11.5" />
      <path d="M7.5 11l4.5 4.5L16.5 11" />
      <path d="M4.5 18.5h15" />
    </svg>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M4.5 12h15" />
      <path d="M13.5 6.5l6 5.5-6 5.5" />
    </svg>
  );
}
