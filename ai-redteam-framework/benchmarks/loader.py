"""
benchmarks/loader.py

Loads benchmark-driven adversarial prompts from benchmarks/datasets/*.json.

Ships with small illustrative samples for JailbreakBench, HarmBench, and
AdvBench shapes (clearly labeled as placeholders — see each file's
"description" field for where to plug in the real, full datasets), plus a
"custom" dataset meant for an organization's own known-risk prompts.

Benchmark-driven testing and autonomous generation are independent:
this loader has zero dependency on attacks/attack_generator.py and can be
used standalone (e.g. `BenchmarkLoader().load_all(objective)`).

LLM CALL: none. Pure file I/O and filtering.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from core.types import ObjectiveProfile

_DATASET_DIR = os.path.join(os.path.dirname(__file__), "datasets")

_FILES = {
    "custom": "custom_sample.json",
    "jailbreakbench": "jailbreakbench_sample.json",
    "harmbench": "harmbench_sample.json",
    "advbench": "advbench_sample.json",
}


class BenchmarkLoader:
    def __init__(self, dataset_dir: str = _DATASET_DIR, enabled: Optional[list[str]] = None):
        self.dataset_dir = dataset_dir
        # Default: only "custom" — the others are illustrative placeholders,
        # so we don't silently burn budget testing toy examples unless asked.
        self.enabled = enabled or ["custom"]

    def load(self, dataset_name: str) -> list[dict]:
        filename = _FILES.get(dataset_name)
        if not filename:
            raise ValueError(
                f"Unknown benchmark '{dataset_name}'. Known: {list(_FILES)}"
            )
        path = os.path.join(self.dataset_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", [])
        for e in entries:
            e["dataset"] = dataset_name
        return entries

    def load_all(self, objective: Optional[ObjectiveProfile] = None) -> list[dict]:
        """Loads every enabled dataset, optionally filtering out entries
        whose category doesn't matter for a given objective (kept broad
        by default — enterprise chatbots should defend against all
        categories, not just objective-specific ones)."""
        out: list[dict] = []
        for name in self.enabled:
            out.extend(self.load(name))
        return out
