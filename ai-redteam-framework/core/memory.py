"""
core/memory.py

Memory is the framework's record of everything that has happened in a run:
every attack sent, every response received, every verdict reached.

It does two jobs that directly reduce API cost:

1. `seen_hash()` — stops the same (or a near-duplicate, post-normalization)
   prompt from being sent to the target or judged twice.
2. `get_cached_verdict()` — if an identical prompt was already judged,
   reuse that verdict instead of paying for another LLM Judge call.

Pure Python. No LLM calls. No network calls.
Backed by an append-only JSONL file so a run can be resumed or audited.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Optional

from core.interfaces import MemoryStore
from core.types import AttackRecord, JudgeResult, Severity, VerdictSource


class JsonlMemoryStore(MemoryStore):
    """Simple, dependency-free memory store. Swap for Redis/Postgres later
    without changing anything else in the framework — this class is the
    only thing that knows about the storage format."""

    def __init__(self, path: str = "output/memory.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._records: list[AttackRecord] = []
        self._hash_to_verdict: dict[str, JudgeResult] = {}
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
                    record = _row_to_record(row)
                    self._records.append(record)
                    self._hash_to_verdict[record.attack.content_hash()] = record.verdict
                except (json.JSONDecodeError, KeyError):
                    continue  # skip corrupt lines rather than crash a run

    def add(self, record: AttackRecord) -> None:
        self._records.append(record)
        self._hash_to_verdict[record.attack.content_hash()] = record.verdict
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(_record_to_row(record)) + "\n")

    def all_records(self) -> list[AttackRecord]:
        return list(self._records)

    def seen_hash(self, content_hash: str) -> bool:
        return content_hash in self._hash_to_verdict

    def get_cached_verdict(self, content_hash: str) -> Optional[JudgeResult]:
        return self._hash_to_verdict.get(content_hash)

    def vulnerability_count(self) -> int:
        return sum(1 for r in self._records if r.verdict.vulnerable)

    def llm_judge_call_count(self) -> int:
        return sum(
            1 for r in self._records if r.verdict.source != VerdictSource.RULE_BASED
        )


def _record_to_row(record: AttackRecord) -> dict:
    d = asdict(record)
    return d


def _row_to_record(row: dict) -> AttackRecord:
    from core.types import AttackPrompt, TargetResponse

    attack = AttackPrompt(**row["attack"])
    response = TargetResponse(**row["response"])
    verdict_row = dict(row["verdict"])
    verdict_row["severity"] = Severity(verdict_row["severity"])
    verdict_row["source"] = VerdictSource(verdict_row["source"])
    verdict = JudgeResult(**verdict_row)
    return AttackRecord(
        attack=attack, response=response, verdict=verdict, timestamp=row["timestamp"]
    )


# ---------------------------------------------------------------------------
# Experience Memory — the autonomous learning loop's growing dataset of
# complete (strategy, prompt, response, analysis, reward) records.
#
# This is intentionally a separate, simpler store from JsonlMemoryStore
# above: the Attack Knowledge Base (knowledge_base/attack_knowledge_base.py)
# is what the policy actually reads from for decision-making (it has
# indexed stats). Experience Memory exists alongside it as the full,
# ordered, human-auditable/replayable log — the same relationship the old
# Memory store had to reporting, just for the richer record shape.
# ---------------------------------------------------------------------------

from core.interfaces import ExperienceMemory  # noqa: E402
from core.types import AttackAnalysis, AttackExperience  # noqa: E402


class JsonlExperienceMemory(ExperienceMemory):
    def __init__(self, path: str = "output/experience_memory.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._experiences: list[AttackExperience] = []
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
                    self._experiences.append(_row_to_experience(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue

    def add(self, experience: AttackExperience) -> None:
        self._experiences.append(experience)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(experience), default=str) + "\n")

    def all_experiences(self) -> list[AttackExperience]:
        return list(self._experiences)

    def get_run_experiences(self, run_id: str) -> list[AttackExperience]:
        return [e for e in self._experiences if e.run_id == run_id]


def _row_to_experience(row: dict) -> AttackExperience:
    from core.types import AttackPrompt, TargetResponse

    prompt = AttackPrompt(**row["prompt"])
    response = TargetResponse(**row["response"])
    analysis_row = dict(row["analysis"])
    analysis_row["severity"] = Severity(analysis_row["severity"])
    analysis_row["source"] = VerdictSource(analysis_row["source"])
    analysis = AttackAnalysis(**analysis_row)
    return AttackExperience(
        strategy=row["strategy"],
        prompt=prompt,
        response=response,
        analysis=analysis,
        reward=row["reward"],
        run_id=row.get("run_id", ""),
        id=row["id"],
        timestamp=row["timestamp"],
    )
