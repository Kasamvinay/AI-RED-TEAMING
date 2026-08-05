"""
reporting/run_registry.py

A small, additive index of past runs. Not a new pipeline stage — it's
data plumbing the API layer needs to answer "what runs have happened"
(GET /runs), "what reports exist" (GET /reports), and "what happened in
run X" (GET /history/{run_id}) without parsing report filenames or
re-reading the whole experience memory on every request.

Same pattern as the rest of the framework (simple JSONL, one row per
run), not a new architectural layer — this is the same kind of thing
core/memory.py already does for experiences, just one level up.

LLM CALL: none.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RunRecord:
    run_id: str
    run_name: str
    objective: str
    target_adapter: str
    status: str = "running"  # "running" | "completed" | "failed"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    max_iterations: int = 0
    total_attacks: int = 0
    successful_attacks: int = 0
    partial_attacks: int = 0
    highest_severity: str = "none"
    technical_report_md: Optional[str] = None
    technical_report_json: Optional[str] = None
    mitigation_report_pdf: Optional[str] = None
    error: Optional[str] = None

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]


class RunRegistry:
    def __init__(self, path: str = "output/runs_registry.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._runs: dict[str, RunRecord] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    self._runs[row["run_id"]] = RunRecord(**row)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

    def _persist_all(self) -> None:
        # Small registry, rewritten in full on every update — simple and
        # correct beats append-only-with-dedup-on-read for something this
        # size (dozens to low hundreds of runs in a demo/PoC context).
        with open(self.path, "w", encoding="utf-8") as f:
            for record in self._runs.values():
                f.write(json.dumps(asdict(record)) + "\n")

    def create(self, run_name: str, objective: str, target_adapter: str, max_iterations: int) -> RunRecord:
        record = RunRecord(
            run_id=RunRecord.new_id(),
            run_name=run_name,
            objective=objective,
            target_adapter=target_adapter,
            max_iterations=max_iterations,
        )
        self._runs[record.run_id] = record
        self._persist_all()
        return record

    def mark_completed(
        self,
        run_id: str,
        total_attacks: int,
        successful_attacks: int,
        partial_attacks: int,
        highest_severity: str,
        technical_report_md: str,
        technical_report_json: str,
        mitigation_report_pdf: Optional[str],
    ) -> None:
        record = self._runs.get(run_id)
        if record is None:
            return
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.total_attacks = total_attacks
        record.successful_attacks = successful_attacks
        record.partial_attacks = partial_attacks
        record.highest_severity = highest_severity
        record.technical_report_md = technical_report_md
        record.technical_report_json = technical_report_json
        record.mitigation_report_pdf = mitigation_report_pdf
        self._persist_all()

    def mark_failed(self, run_id: str, error: str) -> None:
        record = self._runs.get(run_id)
        if record is None:
            return
        record.status = "failed"
        record.completed_at = datetime.now(timezone.utc).isoformat()
        record.error = error
        self._persist_all()

    def get(self, run_id: str) -> Optional[RunRecord]:
        return self._runs.get(run_id)

    def all_runs(self, newest_first: bool = True) -> list[RunRecord]:
        runs = list(self._runs.values())
        runs.sort(key=lambda r: r.started_at, reverse=newest_first)
        return runs
