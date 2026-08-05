"""
reporting/experience_report_generator.py

Report generator for the autonomous learning loop. Same JSON + Markdown
dual-output approach as the legacy reporting/report_generator.py, but
built to make the LEARNING BEHAVIOR visible, not just findings:

- Strategy performance table (avg/best/recent reward, success rate)
- Reward progression across iterations (is the run actually improving?)
- Highest-reward attacks, regardless of which strategy found them
- Newly-generated (LLM/template) vs. benchmark-derived attack counts
- Duplicate attacks avoided/penalized (evidence dedup is working)
- Significant target behavioral changes (AttackAnalysis.behavior_changed)
- Evidence supporting each reported finding

LLM CALL: none. Pure templating.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

from core.types import AttackExperience, Severity, StrategyStats

_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
    Severity.NONE,
]


class ExperienceReportGenerator:
    def __init__(self, output_dir: str = "output/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(
        self,
        experiences: list[AttackExperience],
        strategy_stats: list[StrategyStats],
        run_name: str,
        run_stats: dict | None = None,
    ) -> str:
        run_stats = run_stats or {}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = f"{run_name}_{timestamp}"
        json_path = os.path.join(self.output_dir, f"{base}.json")
        md_path = os.path.join(self.output_dir, f"{base}.md")

        self._write_json(experiences, strategy_stats, run_stats, json_path)
        self._write_markdown(experiences, strategy_stats, run_stats, md_path, run_name)
        return md_path

    # -- JSON --------------------------------------------------------------

    def _write_json(self, experiences, strategy_stats, run_stats, path: str) -> None:
        payload = {
            "summary": self._summary(experiences),
            "run_stats": run_stats,
            "strategy_performance": [asdict(s) for s in strategy_stats],
            "reward_progression": [
                {"iteration": i + 1, "strategy": e.strategy, "reward": e.reward,
                 "outcome": e.analysis.outcome}
                for i, e in enumerate(experiences)
            ],
            "top_rewarded_attacks": [
                self._exp_to_dict(e) for e in self._top_rewarded(experiences, 5)
            ],
            "significant_behavior_changes": [
                self._exp_to_dict(e) for e in experiences if e.analysis.behavior_changed
            ],
            "findings": [self._exp_to_dict(e) for e in experiences if e.analysis.outcome != "failure"],
            "all_experiences": [self._exp_to_dict(e) for e in experiences],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def _exp_to_dict(self, e: AttackExperience) -> dict:
        d = asdict(e)
        d["analysis"]["severity"] = e.analysis.severity.value
        d["analysis"]["source"] = e.analysis.source.value
        return d

    @staticmethod
    def _top_rewarded(experiences: list[AttackExperience], n: int) -> list[AttackExperience]:
        return sorted(experiences, key=lambda e: e.reward, reverse=True)[:n]

    # -- Markdown ----------------------------------------------------------

    def _write_markdown(self, experiences, strategy_stats, run_stats, path: str, run_name: str) -> None:
        summary = self._summary(experiences)
        findings = sorted(
            (e for e in experiences if e.analysis.outcome != "failure"),
            key=lambda e: _SEVERITY_ORDER.index(e.analysis.severity),
        )

        lines: list[str] = []
        lines.append(f"# Autonomous Prompt Injection Report — {run_name}")
        lines.append("")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total attacks executed: **{summary['total']}**")
        lines.append(f"- Successful prompt injections: **{summary['success_count']}**")
        lines.append(f"- Partial successes: **{summary['partial_count']}**")
        lines.append(f"- Complete failures: **{summary['failure_count']}**")
        lines.append(f"- LLM Analyst calls used: **{summary['llm_calls']}** "
                      f"({summary['rule_based_pct']:.0f}% resolved by rule-based analysis alone)")
        if run_stats.get("total_api_calls") is not None:
            lines.append(f"- Total OpenAI API calls this run (generator + target + analyst): "
                          f"**{run_stats['total_api_calls']}**")
            by_role = run_stats.get("api_calls_by_role") or {}
            if by_role:
                role_line = ", ".join(f"{role}={n}" for role, n in by_role.items())
                lines.append(f"  - by role: {role_line}")
        lines.append(f"- Exact-duplicate attacks rejected: **{run_stats.get('exact_duplicates_avoided', 0)}**")
        lines.append(f"- Near-duplicate attacks penalized (allowed but reward-penalized): "
                      f"**{run_stats.get('near_duplicates_penalized', 0)}**")
        lines.append("")

        source_breakdown = run_stats.get("source_breakdown") or {}
        if source_breakdown:
            lines.append("### Attack provenance (newly generated vs. benchmark-derived)")
            lines.append("")
            lines.append("| Source | Count |")
            lines.append("|---|---|")
            for source, count in sorted(source_breakdown.items(), key=lambda kv: -kv[1]):
                lines.append(f"| {source} | {count} |")
            lines.append("")

        lines.append("## Strategy performance (RL policy state)")
        lines.append("")
        lines.append("What the reinforcement-learning policy has learned about which prompt "
                      "injection strategies work against this target — average reward, best "
                      "single result, recent trend (last 5 attempts), and current failure streak.")
        lines.append("")
        lines.append("| Strategy | Attempts | Successes | Success rate | Avg reward | Best reward | Recent trend | Failure streak |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in sorted(strategy_stats, key=lambda s: s.avg_reward, reverse=True):
            success_rate = f"{100 * s.successes / s.attempts:.0f}%" if s.attempts else "—"
            lines.append(
                f"| {s.strategy} | {s.attempts} | {s.successes} | {success_rate} | "
                f"{s.avg_reward:+.2f} | {s.best_reward:+.2f} | {s.recent_avg_reward:+.2f} | "
                f"{s.consecutive_failures} |"
            )
        lines.append("")

        lines.append("## Reward progression")
        lines.append("")
        lines.append("Reward per iteration, in the order attacks were executed — a run where "
                      "the framework is adapting should trend upward or show the policy "
                      "converging on a few high-reward strategies rather than staying flat/random.")
        lines.append("")
        lines.append("| # | Strategy | Outcome | Reward |")
        lines.append("|---|---|---|---|")
        for i, e in enumerate(experiences, start=1):
            lines.append(f"| {i} | {e.strategy} | {e.analysis.outcome} | {e.reward:+.2f} |")
        lines.append("")

        top = self._top_rewarded(experiences, 5)
        if top:
            lines.append("## Highest-reward attacks")
            lines.append("")
            for i, e in enumerate(top, start=1):
                lines.append(f"**{i}. reward={e.reward:+.2f}** — strategy `{e.strategy}` "
                              f"(source: `{e.prompt.source}`, outcome: {e.analysis.outcome})")
                lines.append("")
                lines.append("```")
                lines.append(e.prompt.text[:500])
                lines.append("```")
                lines.append("")

        behavior_changes = [e for e in experiences if e.analysis.behavior_changed]
        if behavior_changes:
            lines.append("## Significant target behavioral changes")
            lines.append("")
            lines.append("Attempts where the target's response differed meaningfully from its "
                          "prior response to the same strategy — worth a human look even when "
                          "the outcome wasn't a clean success.")
            lines.append("")
            for e in behavior_changes[:10]:
                lines.append(f"- **{e.strategy}** (novelty {e.analysis.novelty:.2f}, "
                              f"outcome {e.analysis.outcome}): {e.analysis.observed_behavior or e.analysis.explanation}")
            lines.append("")

        lines.append("## Findings")
        lines.append("")
        if not findings:
            lines.append("_No successful or partial prompt injections were confirmed in this run._")
        for i, e in enumerate(findings, start=1):
            a = e.analysis
            lines.append(f"### Finding {i}: {a.outcome.upper()} ({a.severity.value}) — {e.strategy}")
            lines.append("")
            lines.append(f"- **Variant:** `{e.prompt.technique}`  |  **Source:** `{e.prompt.source}`")
            lines.append(f"- **Score:** {a.score:.2f}  |  **Confidence:** {a.confidence:.2f}  "
                          f"|  **Analysis source:** `{a.source.value}`")
            lines.append(f"- **Reward:** {e.reward:+.2f}")
            lines.append(f"- **Instructions overridden:** {a.instructions_overridden}  "
                          f"|  **Behavior changed:** {a.behavior_changed}  |  **Novelty:** {a.novelty:.2f}")
            lines.append(f"- **Observed behavior:** {a.observed_behavior or 'n/a'}")
            lines.append(f"- **Reason:** {a.explanation}")
            if a.evidence:
                lines.append(f"- **Evidence:** {'; '.join(a.evidence)}")
            if a.defense_triggered:
                lines.append(f"- **Defense triggered:** {a.defense_triggered}")
            if a.recommendation:
                lines.append(f"- **Recommendation for next attempt:** {a.recommendation}")
            if a.tags:
                lines.append(f"- **Tags:** {', '.join(a.tags)}")
            lines.append("")
            lines.append("**Attack prompt:**")
            lines.append("```")
            lines.append(e.prompt.text)
            lines.append("```")
            lines.append("")
            lines.append("**Target response:**")
            lines.append("```")
            lines.append(e.response.text[:2000])
            lines.append("```")
            lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # -- shared -----------------------------------------------------------

    @staticmethod
    def _summary(experiences: list[AttackExperience]) -> dict:
        total = len(experiences)
        outcomes = Counter(e.analysis.outcome for e in experiences)
        llm_calls = sum(1 for e in experiences if e.analysis.source.value != "rule_based")
        rule_based_pct = 100.0 * (total - llm_calls) / total if total else 100.0
        return {
            "total": total,
            "success_count": outcomes.get("success", 0),
            "partial_count": outcomes.get("partial", 0),
            "failure_count": outcomes.get("failure", 0),
            "llm_calls": llm_calls,
            "rule_based_pct": rule_based_pct,
        }
