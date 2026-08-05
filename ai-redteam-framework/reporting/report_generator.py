"""
reporting/report_generator.py

Turns a list of AttackRecords into a structured vulnerability report:
- A machine-readable JSON file (for CI pipelines / dashboards)
- A human-readable Markdown file (for AI engineers / QA / security teams)

LLM CALL: none. Pure string templating and JSON serialization.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

from core.interfaces import ReportGenerator
from core.types import AttackRecord, Severity

_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
    Severity.NONE,
]


class MarkdownJsonReportGenerator(ReportGenerator):
    def __init__(self, output_dir: str = "output/reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, records: list[AttackRecord], run_name: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = f"{run_name}_{timestamp}"

        json_path = os.path.join(self.output_dir, f"{base}.json")
        md_path = os.path.join(self.output_dir, f"{base}.md")

        self._write_json(records, json_path)
        self._write_markdown(records, md_path, run_name)

        return md_path

    # -- JSON ------------------------------------------------------------

    def _write_json(self, records: list[AttackRecord], path: str) -> None:
        payload = {
            "summary": self._summary(records),
            "findings": [self._record_to_dict(r) for r in records if r.verdict.vulnerable],
            "all_records": [self._record_to_dict(r) for r in records],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def _record_to_dict(self, record: AttackRecord) -> dict:
        d = asdict(record)
        d["verdict"]["severity"] = record.verdict.severity.value
        d["verdict"]["source"] = record.verdict.source.value
        return d

    # -- Markdown ----------------------------------------------------------

    def _write_markdown(self, records: list[AttackRecord], path: str, run_name: str) -> None:
        summary = self._summary(records)
        findings = sorted(
            (r for r in records if r.verdict.vulnerable),
            key=lambda r: _SEVERITY_ORDER.index(r.verdict.severity),
        )

        lines: list[str] = []
        lines.append(f"# AI Red Team Report — {run_name}")
        lines.append("")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total attacks executed: **{summary['total']}**")
        lines.append(f"- Vulnerabilities found: **{summary['vulnerable_count']}**")
        lines.append(f"- LLM Judge calls used: **{summary['llm_judge_calls']}** "
                      f"(of {summary['total']} total evaluations — "
                      f"{summary['rule_based_pct']:.0f}% resolved by Rule-Based Judge alone)")
        lines.append("")
        lines.append("### Severity breakdown")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|---|---|")
        for sev in _SEVERITY_ORDER:
            count = summary["severity_counts"].get(sev.value, 0)
            if count:
                lines.append(f"| {sev.value} | {count} |")
        lines.append("")
        lines.append("### Category breakdown")
        lines.append("")
        lines.append("| Category | Vulnerable findings |")
        lines.append("|---|---|")
        for category, count in summary["category_counts"].items():
            lines.append(f"| {category} | {count} |")
        lines.append("")

        lines.append("## Findings")
        lines.append("")
        if not findings:
            lines.append("_No vulnerabilities were confirmed in this run._")
        for i, record in enumerate(findings, start=1):
            a, r, v = record.attack, record.response, record.verdict
            lines.append(f"### Finding {i}: {v.severity.value.upper()} — {a.category}")
            lines.append("")
            lines.append(f"- **Technique:** `{a.technique}`")
            lines.append(f"- **Source:** `{a.source}`")
            lines.append(f"- **Judge source:** `{v.source.value}` (confidence {v.confidence:.2f})")
            lines.append(f"- **Reason:** {v.reason}")
            if v.matched_signals:
                lines.append(f"- **Matched signals:** {', '.join(v.matched_signals)}")
            lines.append("")
            lines.append("**Attack prompt:**")
            lines.append("```")
            lines.append(a.text)
            lines.append("```")
            lines.append("")
            lines.append("**Target response:**")
            lines.append("```")
            lines.append(r.text[:2000])
            lines.append("```")
            lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # -- shared -----------------------------------------------------------

    @staticmethod
    def _summary(records: list[AttackRecord]) -> dict:
        total = len(records)
        vulnerable = [r for r in records if r.verdict.vulnerable]
        severity_counts = Counter(r.verdict.severity.value for r in vulnerable)
        category_counts = Counter(r.attack.category for r in vulnerable)
        llm_calls = sum(1 for r in records if r.verdict.source.value != "rule_based")
        rule_based_pct = 100.0 * (total - llm_calls) / total if total else 100.0

        return {
            "total": total,
            "vulnerable_count": len(vulnerable),
            "severity_counts": dict(severity_counts),
            "category_counts": dict(category_counts),
            "llm_judge_calls": llm_calls,
            "rule_based_pct": rule_based_pct,
        }
