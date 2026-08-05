"""
main.py

CLI entry point. Wires together an adapter, the hybrid judge, the
generator/refiner, memory, and the report generator, then runs the
Orchestrator loop end to end.

Usage:
    python main.py                                   # mock target, customer_support objective
    python main.py --target openai --objective banking_assistant
    python main.py --target rest_api --rest-url https://internal-bot.example.com/chat
    python main.py --max-iterations 10 --max-llm-calls 5

This file is intentionally the only place that reads CLI args / env vars
and decides which concrete adapter/judge implementations to instantiate.
Everything downstream of this file talks only to the interfaces in
core/interfaces.py.
"""

from __future__ import annotations

import argparse
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the current directory, if present, into os.environ
except ImportError:
    pass  # python-dotenv not installed — fall back to real environment variables only

from attacks.attack_generator import TemplateAttackGenerator
from attacks.attack_refiner import MutationAttackRefiner
from benchmarks.loader import BenchmarkLoader
from config.settings import load_config
from core.memory import JsonlMemoryStore
from core.orchestrator import Orchestrator
from core.types import RunConfig
from judge.hybrid_judge import HybridJudge
from judge.llm_judge import LLMJudge
from judge.rule_based_judge import RuleBasedJudge
from objectives.profiles import load_objective
from reporting.report_generator import MarkdownJsonReportGenerator


class _NullLLMJudge:
    """Stand-in used when max_llm_calls == 0. HybridJudge checks the call
    budget BEFORE invoking the LLM judge, so `evaluate` here should never
    actually be called — this only exists so we don't have to import the
    `openai` package (or require an API key) for pure rule-based runs."""

    def evaluate(self, attack, response, objective):  # pragma: no cover
        raise RuntimeError(
            "LLM Judge was invoked despite max_llm_calls == 0 — this is a bug."
        )


def build_adapter(name: str, config: dict, objective_system_prompt: str):
    if name == "mock":
        from adapters.mock_adapter import MockAdapter
        return MockAdapter()
    if name == "openai":
        from adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(
            model=config["target"]["openai_model"],
            system_prompt=objective_system_prompt,
        )
    if name == "rest_api":
        from adapters.rest_api_adapter import RestApiAdapter
        return RestApiAdapter(url=config["target"]["rest_api_url"])
    raise ValueError(f"Unknown target adapter '{name}'. Use: mock | openai | rest_api")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous AI Red Teaming Framework")
    parser.add_argument("--objective", default=None, help="customer_support | banking_assistant | hr_assistant | generic")
    parser.add_argument("--target", default=None, help="mock | openai | rest_api")
    parser.add_argument("--rest-url", default=None, help="URL for the rest_api target adapter")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-llm-calls", type=int, default=None)
    parser.add_argument("--run-name", default="redteam_run")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    objective_name = args.objective or config["objective"]
    target_name = args.target or config["target"]["adapter"]
    if args.rest_url:
        config["target"]["rest_api_url"] = args.rest_url

    objective = load_objective(objective_name)
    adapter = build_adapter(target_name, config, objective.system_prompt)

    rule_based = RuleBasedJudge(confidence_threshold=config["judge"]["confidence_threshold"])
    max_llm_calls = args.max_llm_calls if args.max_llm_calls is not None else config["judge"]["max_llm_calls"]

    # LLMJudge (and therefore the `openai` package + API key) is only
    # constructed if the budget is nonzero — a max-llm-calls=0 run (or any
    # environment without the openai package installed) can still do a
    # fully rule-based-only run without ever importing openai.
    llm_judge = LLMJudge(model=config["judge"]["model"]) if max_llm_calls > 0 else _NullLLMJudge()
    judge = HybridJudge(
        rule_based=rule_based,
        llm_judge=llm_judge,
        confidence_threshold=config["judge"]["confidence_threshold"],
        max_llm_calls=max_llm_calls,
    )

    generator = TemplateAttackGenerator(
        benchmark_loader=BenchmarkLoader(enabled=config["run"]["benchmark_names"])
    )
    refiner = MutationAttackRefiner()
    memory = JsonlMemoryStore(path=config["output"]["memory_path"])
    report_generator = MarkdownJsonReportGenerator(output_dir=config["output"]["report_dir"])

    run_config = RunConfig(
        objective=objective,
        max_iterations=args.max_iterations or config["run"]["max_iterations"],
        max_llm_judge_calls=max_llm_calls,
        rule_based_confidence_threshold=config["judge"]["confidence_threshold"],
        use_benchmarks=config["run"]["use_benchmarks"],
        benchmark_names=config["run"]["benchmark_names"],
        autonomous_generation=config["run"]["autonomous_generation"],
        refine_top_n=config["run"]["refine_top_n"],
        stop_on_critical=config["run"]["stop_on_critical"],
    )

    orchestrator = Orchestrator(
        adapter=adapter,
        judge=judge,
        generator=generator,
        refiner=refiner,
        memory=memory,
        report_generator=report_generator,
        config=run_config,
    )

    report_path = orchestrator.run(run_name=args.run_name)
    print(f"\nReport written to: {report_path}")
    print(f"LLM Judge calls used: {judge.llm_calls_made} / {max_llm_calls}")


if __name__ == "__main__":
    main()
