"""
tests/test_autonomous_pipeline_offline.py

Fully offline smoke test for the autonomous prompt-injection pipeline:
MockAdapter + RuleBasedAttackAnalyzer only (no LLM analyst — max_llm_calls
is never reached because llm_analyst=None). Validates the whole
Knowledge Base -> Strategy Planner -> Prompt Generator -> Target ->
Attack Analyst -> Experience Memory -> policy-update loop with zero
network calls and zero API cost, and confirms the Knowledge Base actually
accumulates statistics across iterations (the "learning" part).

Run with: python -m pytest tests/ -v
or directly: python tests/test_autonomous_pipeline_offline.py
"""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.mock_adapter import MockAdapter
from attacks.attack_refiner import KnowledgeGuidedAttackRefiner
from attacks.policy import EpsilonGreedyPolicy
from attacks.prompt_generator import TemplatePromptGenerator
from attacks.strategy_planner import BanditStrategyPlanner
from benchmarks.loader import BenchmarkLoader
from core.memory import JsonlExperienceMemory
from core.orchestrator import AutonomousOrchestrator
from core.types import PROMPT_INJECTION_STRATEGIES, RunConfig
from judge.attack_analyst import HybridAttackAnalyst, RuleBasedAttackAnalyzer
from knowledge_base.attack_knowledge_base import SQLiteAttackKnowledgeBase
from objectives.profiles import load_objective
from reporting.experience_report_generator import ExperienceReportGenerator


def test_autonomous_pipeline_runs_offline(tmp_output="output/test_autonomous_run"):
    if os.path.exists(tmp_output):
        shutil.rmtree(tmp_output)
    os.makedirs(tmp_output, exist_ok=True)

    objective = load_objective("customer_support")
    adapter = MockAdapter()

    kb = SQLiteAttackKnowledgeBase(path=os.path.join(tmp_output, "kb.sqlite3"))
    kb.bootstrap_from_benchmarks(BenchmarkLoader(enabled=["custom"]).load_all(objective))

    policy = EpsilonGreedyPolicy(exploration_rate=0.25, rng=__import__("random").Random(42))
    planner = BanditStrategyPlanner(knowledge_base=kb, policy=policy)
    generator = TemplatePromptGenerator(knowledge_base=kb, exploration_rate=0.25)
    refiner = KnowledgeGuidedAttackRefiner(strategy_planner=planner, prompt_generator=generator)

    analyst = HybridAttackAnalyst(
        rule_based=RuleBasedAttackAnalyzer(),
        llm_analyst=None,  # forces pure rule-based path, no API key needed
        confidence_threshold=0.75,
        max_llm_calls=0,
    )

    experience_memory = JsonlExperienceMemory(path=os.path.join(tmp_output, "experiences.jsonl"))
    reporter = ExperienceReportGenerator(output_dir=os.path.join(tmp_output, "reports"))

    config = RunConfig(objective=objective, max_iterations=18, max_analysis_llm_calls=0)
    orchestrator = AutonomousOrchestrator(
        adapter=adapter,
        knowledge_base=kb,
        refiner=refiner,
        analyst=analyst,
        experience_memory=experience_memory,
        report_generator=reporter,
        config=config,
    )

    report_path = orchestrator.run(run_name="offline_autonomous_test")

    assert os.path.exists(report_path)

    experiences = experience_memory.all_experiences()
    assert len(experiences) > 0
    assert len(experiences) <= config.max_iterations

    # Every canonical strategy should have been given at least one attempt
    # (cold-start forcing in EpsilonGreedyPolicy) within 18 iterations.
    stats = {s.strategy: s for s in kb.all_strategy_stats()}
    for strategy in PROMPT_INJECTION_STRATEGIES:
        assert strategy in stats, f"missing strategy stats for {strategy}"
    assert all(s.attempts >= 1 for s in stats.values()), "cold start did not try every strategy"

    # MockAdapter is designed to leak under instruction-override-style
    # prompts, so at least one strategy should show a nonzero success rate.
    assert any(s.successes > 0 for s in stats.values()), "expected at least one successful strategy"

    # Knowledge base persistence: reopening the same path should carry
    # over cumulative attempts (the actual "learning across runs" claim).
    kb.close()
    kb2 = SQLiteAttackKnowledgeBase(path=os.path.join(tmp_output, "kb.sqlite3"))
    total_attempts_before = sum(s.attempts for s in stats.values())
    total_attempts_after = sum(s.attempts for s in kb2.all_strategy_stats())
    assert total_attempts_after == total_attempts_before, "knowledge base did not persist"
    kb2.close()

    print(f"OK: {len(experiences)} experiences, report at {report_path}")
    shutil.rmtree(tmp_output)


if __name__ == "__main__":
    test_autonomous_pipeline_runs_offline()
