"""
runner.py

Shared pipeline construction, used by BOTH:
- main.py (CLI)
- api/app.py (REST API backing the demo frontend)

This is a pure extraction of the wiring logic that used to live entirely
inside main.py's main() — no behavior changed, no new decisions made.
The API layer must never re-implement or duplicate this wiring; it calls
`build_pipeline()` exactly like the CLI does, just with an optional
`on_event` callback for live status and without the argparse/print layer.

Contains no business logic of its own — only imports and wires together
the existing framework components.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from attacks.attack_refiner import KnowledgeGuidedAttackRefiner
from attacks.policy import EpsilonGreedyPolicy
from attacks.prompt_generator import LLMPromptGenerator, TemplatePromptGenerator
from attacks.reward import RewardConfig
from attacks.strategy_planner import BanditStrategyPlanner
from benchmarks.loader import BenchmarkLoader
from core.call_tracker import ApiCallTracker
from core.memory import JsonlExperienceMemory
from core.orchestrator import AutonomousOrchestrator
from core.types import RunConfig
from judge.attack_analyst import HybridAttackAnalyst, RuleBasedAttackAnalyzer
from knowledge_base.attack_knowledge_base import SQLiteAttackKnowledgeBase
from llm.factory import LLMFactory
from objectives.profiles import load_objective
from reporting.experience_report_generator import ExperienceReportGenerator


def build_adapter(name: str, config: dict, objective_system_prompt: str, api_call_tracker: ApiCallTracker):
    if name == "mock":
        from adapters.mock_adapter import MockAdapter
        return MockAdapter()
    if name == "openai":
        from adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(
            model=config["target"]["openai_model"],
            system_prompt=objective_system_prompt,
            temperature=config["target"].get("openai_temperature", 0.7),
            max_tokens=config["target"].get("openai_max_tokens", 400),
            api_call_tracker=api_call_tracker,
        )
    if name == "rest_api":
        from adapters.rest_api_adapter import RestApiAdapter
        return RestApiAdapter(url=config["target"]["rest_api_url"])
    if name == "acme_supportbot":
        from adapters.acme_supportbot_adapter import AcmeSupportBotAdapter
        return AcmeSupportBotAdapter(
            base_url=config["target"].get("base_url", "http://localhost:8000"),
            timeout_seconds=config["target"].get("timeout_seconds", 300.0),
            reset_between_attacks=config["target"].get("reset_between_attacks", True),
        )
    raise ValueError(f"Unknown target adapter '{name}'. Use: mock | openai | rest_api | acme_supportbot")


@dataclass
class BuiltPipeline:
    orchestrator: AutonomousOrchestrator
    knowledge_base: SQLiteAttackKnowledgeBase
    analyst: HybridAttackAnalyst
    api_call_tracker: ApiCallTracker
    run_config: RunConfig
    objective_name: str
    target_name: str


def build_pipeline(
    config: dict,
    objective_name: Optional[str] = None,
    target_name: Optional[str] = None,
    rest_url: Optional[str] = None,
    prompt_generator_kind: Optional[str] = None,
    max_iterations: Optional[int] = None,
    max_llm_calls: Optional[int] = None,
    max_total_api_calls: Optional[int] = None,
    exploration_rate: Optional[float] = None,
    multi_turn_enabled_override: Optional[bool] = None,
    fresh_kb: bool = False,
    on_event: Optional[Callable] = None,
) -> BuiltPipeline:
    objective_name = objective_name or config["objective"]
    target_name = target_name or config["target"]["adapter"]
    if rest_url:
        config["target"]["rest_api_url"] = rest_url

    objective = load_objective(objective_name)

    max_llm_calls = max_llm_calls if max_llm_calls is not None else config["judge"]["max_analysis_llm_calls"]
    exploration_rate = exploration_rate if exploration_rate is not None else config["run"]["exploration_rate"]
    max_total_api_calls = max_total_api_calls if max_total_api_calls is not None else config["run"]["max_total_api_calls"]
    generator_kind = prompt_generator_kind or config["run"]["prompt_generator"]
    multi_turn_enabled = (
        config["run"]["multi_turn_enabled"] if multi_turn_enabled_override is None else multi_turn_enabled_override
    )
    kb_path = config["output"]["kb_path"]
    experience_path = config["output"]["experience_memory_path"]

    if fresh_kb:
        for p in (kb_path, experience_path):
            if os.path.exists(p):
                os.remove(p)

    # --- Global, shared API call budget across ALL THREE roles ---
    api_call_tracker = ApiCallTracker()

    adapter = build_adapter(target_name, config, objective.system_prompt, api_call_tracker)

    # --- Attack Knowledge Base, bootstrapped from benchmark datasets ---
    knowledge_base = SQLiteAttackKnowledgeBase(path=kb_path)
    benchmark_loader = BenchmarkLoader(enabled=config["run"]["benchmark_names"])
    if config["run"]["use_benchmarks"]:
        knowledge_base.bootstrap_from_benchmarks(benchmark_loader.load_all(objective))

    # --- Strategy Planner (RL policy) + Prompt Generator (Attacker role) ---
    policy = EpsilonGreedyPolicy(exploration_rate=exploration_rate)
    strategy_planner = BanditStrategyPlanner(knowledge_base=knowledge_base, policy=policy)

    if generator_kind == "llm":
        generator_llm_client = LLMFactory.create(
            temperature=config["generator"]["temperature"],
            max_tokens=config["generator"]["max_tokens"],
        )
        prompt_generator = LLMPromptGenerator(
            knowledge_base=knowledge_base,
            llm_client=generator_llm_client,
            near_duplicate_threshold=config["run"]["near_duplicate_threshold"],
            max_retries=config["generator"]["max_retries_on_near_duplicate"],
            api_call_tracker=api_call_tracker,
        )
    else:
        prompt_generator = TemplatePromptGenerator(knowledge_base=knowledge_base, exploration_rate=exploration_rate)

    refiner = KnowledgeGuidedAttackRefiner(strategy_planner=strategy_planner, prompt_generator=prompt_generator)

    # --- Attack Analyst role: rule-based first, LLM only if budget > 0 ---
    rule_based_analyzer = RuleBasedAttackAnalyzer(knowledge_base=knowledge_base)
    llm_analyst = None
    if max_llm_calls > 0:
        from judge.attack_analyst import LLMAttackAnalyst
        analyst_llm_client = LLMFactory.create(
            temperature=config["judge"]["temperature"],
            max_tokens=config["judge"]["max_tokens"],
        )
        llm_analyst = LLMAttackAnalyst(
            llm_client=analyst_llm_client,
            knowledge_base=knowledge_base,
        )
        # Wrap so LLM Analyst calls also count against the global budget.
        _orig_analyze = llm_analyst.analyze

        def _tracked_analyze(attack, response, obj, _orig=_orig_analyze):
            result = _orig(attack, response, obj)
            api_call_tracker.record(role="analyst")
            return result

        llm_analyst.analyze = _tracked_analyze  # type: ignore[method-assign]

    analyst = HybridAttackAnalyst(
        rule_based=rule_based_analyzer,
        llm_analyst=llm_analyst,
        confidence_threshold=config["judge"]["confidence_threshold"],
        max_llm_calls=max_llm_calls,
    )

    experience_memory = JsonlExperienceMemory(path=experience_path)
    report_generator = ExperienceReportGenerator(output_dir=config["output"]["report_dir"])

    run_config = RunConfig(
        objective=objective,
        max_iterations=max_iterations or config["run"]["max_iterations"],
        max_analysis_llm_calls=max_llm_calls,
        rule_based_confidence_threshold=config["judge"]["confidence_threshold"],
        use_benchmarks=config["run"]["use_benchmarks"],
        benchmark_names=config["run"]["benchmark_names"],
        stop_on_critical=config["run"]["stop_on_critical"],
        exploration_rate=exploration_rate,
        kb_path=kb_path,
        experience_memory_path=experience_path,
        prompt_generator=generator_kind,
        multi_turn_enabled=multi_turn_enabled,
        multi_turn_max_turns=config["run"]["multi_turn_max_turns"],
        near_duplicate_threshold=config["run"]["near_duplicate_threshold"],
        max_total_api_calls=max_total_api_calls,
    )

    orchestrator = AutonomousOrchestrator(
        adapter=adapter,
        knowledge_base=knowledge_base,
        refiner=refiner,
        analyst=analyst,
        experience_memory=experience_memory,
        report_generator=report_generator,
        config=run_config,
        reward_config=RewardConfig(),
        api_call_tracker=api_call_tracker,
        on_event=on_event,
    )

    return BuiltPipeline(
        orchestrator=orchestrator,
        knowledge_base=knowledge_base,
        analyst=analyst,
        api_call_tracker=api_call_tracker,
        run_config=run_config,
        objective_name=objective_name,
        target_name=target_name,
    )
