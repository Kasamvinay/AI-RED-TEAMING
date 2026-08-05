"""
tests/test_pipeline_offline.py

Fully offline smoke test: MockAdapter + RuleBasedJudge only (LLM judge is
never invoked because confidence_threshold=0.0 makes rule-based verdicts
always "confident enough"). Validates the whole Attack -> Evaluate ->
Learn -> Refine -> Report loop with zero network calls and zero API cost.

Run with: python -m pytest tests/ -v
or directly: python tests/test_pipeline_offline.py
"""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.mock_adapter import MockAdapter
from attacks.attack_generator import TemplateAttackGenerator
from attacks.attack_refiner import MutationAttackRefiner
from benchmarks.loader import BenchmarkLoader
from core.interfaces import Judge
from core.memory import JsonlMemoryStore
from core.orchestrator import Orchestrator
from core.types import RunConfig
from judge.rule_based_judge import RuleBasedJudge
from objectives.profiles import load_objective
from reporting.report_generator import MarkdownJsonReportGenerator


class RuleOnlyJudge(Judge):
    """Wraps RuleBasedJudge so this test never needs an OpenAI key."""

    def __init__(self):
        self._rb = RuleBasedJudge()

    def evaluate(self, attack, response, objective):
        return self._rb.evaluate(attack, response, objective)

    @property
    def llm_calls_made(self):
        return 0


def test_full_pipeline_runs_offline(tmp_output="output/test_run"):
    if os.path.exists(tmp_output):
        shutil.rmtree(tmp_output)
    os.makedirs(tmp_output, exist_ok=True)

    objective = load_objective("customer_support")
    adapter = MockAdapter()
    judge = RuleOnlyJudge()
    generator = TemplateAttackGenerator(benchmark_loader=BenchmarkLoader(enabled=["custom"]))
    refiner = MutationAttackRefiner()
    memory = JsonlMemoryStore(path=os.path.join(tmp_output, "memory.jsonl"))
    reporter = MarkdownJsonReportGenerator(output_dir=os.path.join(tmp_output, "reports"))

    # NOTE: TemplateAttackGenerator shuffles its prompt pool without a
    # fixed seed, so a small max_iterations occasionally samples a batch
    # with no leak-triggering prompt. The custom benchmark set (8 entries,
    # several of which trigger MockAdapter's leak) plus the generator's
    # own template expansion gives a large enough pool that iterating all
    # of it reliably includes at least one hit.
    config = RunConfig(objective=objective, max_iterations=25, max_llm_judge_calls=0)
    orchestrator = Orchestrator(adapter, judge, generator, refiner, memory, reporter, config)

    report_path = orchestrator.run(run_name="offline_test")

    assert os.path.exists(report_path)
    records = memory.all_records()
    assert len(records) > 0
    assert len(records) <= config.max_iterations
    # MockAdapter is designed to leak under instruction-override-style prompts,
    # so at least one vulnerability should be found by the rule-based judge.
    assert any(r.verdict.vulnerable for r in records), "expected at least one finding from MockAdapter"

    print(f"OK: {len(records)} records, report at {report_path}")
    shutil.rmtree(tmp_output)


if __name__ == "__main__":
    test_full_pipeline_runs_offline()
