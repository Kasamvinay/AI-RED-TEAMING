"""
main.py

CLI entry point for the AUTONOMOUS PROMPT INJECTION pipeline:

    Benchmark Knowledge -> Attack Knowledge Base -> Strategy Planner
    -> LLM Prompt Generator -> Target Adapter -> Target Model
    -> Attack Analyst -> Reward + Experience Update -> RL Policy/Strategy
    Update -> next attack (loop)

Three logically isolated LLM roles can all be active in one run:
  1. Attacker / Prompt Generator  (attacks/prompt_generator.py::LLMPromptGenerator)
  2. Target Model                 (adapters/openai_adapter.py::OpenAIAdapter, or any other target adapter)
  3. Attack Analyst / Judge       (judge/attack_analyst.py::LLMAttackAnalyst)
Roles 1 and 3 (the framework's own reasoning) go through the provider-
agnostic llm/ package — see llm/factory.py — so LLM_PROVIDER in .env
picks OpenAI, Gemini, or Groq for both, independent of whichever system
is being tested as the target. Each role still gets its own client
instance, its own system prompt, and its own single-purpose context —
none of them see each other's system prompts or conversation history.

Pipeline construction itself lives in runner.py, shared with api/app.py
(the REST API backing the demo frontend) — this file is just the CLI's
argument parsing and console output around that shared logic.

The pre-existing single-pass pipeline (Attack Generator -> Judge ->
Memory -> mutation-based Refiner) still exists and still works — it's
preserved in main_legacy.py.

Usage:
    python main.py                                       # mock target + template generator, offline, $0 cost
    python main.py --target openai                       # full 3-role experimental run
    python main.py --target openai --objective banking_assistant --max-iterations 30
    python main.py --target rest_api --rest-url https://internal-bot.example.com/chat --prompt-generator llm

    # REST API + demo frontend:
    uvicorn api.app:app --reload

    # legacy single-pass pipeline, unchanged:
    python main_legacy.py --target mock
"""

from __future__ import annotations

import argparse
import logging
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the current directory, if present, into os.environ
except ImportError:
    pass  # python-dotenv not installed — fall back to real environment variables only

from config.settings import load_config
from runner import build_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Prompt Injection Testing Framework")
    parser.add_argument("--objective", default=None, help="customer_support | banking_assistant | hr_assistant | generic")
    parser.add_argument("--target", default=None, help="mock | openai | rest_api | acme_supportbot")
    parser.add_argument("--rest-url", default=None, help="URL for the rest_api target adapter")
    parser.add_argument("--prompt-generator", default=None, choices=["llm", "template"],
                         help="llm (default this phase) or template (deterministic, $0)")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-llm-calls", type=int, default=None, help="cap on Attack Analyst LLM escalations")
    parser.add_argument("--max-total-api-calls", type=int, default=None,
                         help="hard safety cap across generator+target+analyst combined")
    parser.add_argument("--exploration-rate", type=float, default=None, help="epsilon for the strategy bandit policy")
    parser.add_argument("--no-multi-turn", action="store_true", help="disable multi_turn_escalation sessions")
    parser.add_argument("--run-name", default="prompt_injection_run")
    parser.add_argument("--fresh-kb", action="store_true", help="delete any existing knowledge base/experience memory before this run")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    pipeline = build_pipeline(
        config=config,
        objective_name=args.objective,
        target_name=args.target,
        rest_url=args.rest_url,
        prompt_generator_kind=args.prompt_generator,
        max_iterations=args.max_iterations,
        max_llm_calls=args.max_llm_calls,
        max_total_api_calls=args.max_total_api_calls,
        exploration_rate=args.exploration_rate,
        multi_turn_enabled_override=(False if args.no_multi_turn else None),
        fresh_kb=args.fresh_kb,
    )

    run_id = uuid.uuid4().hex[:12]
    report_path = pipeline.orchestrator.run(run_name=args.run_name, run_id=run_id)

    tracker = pipeline.api_call_tracker
    print(f"\nReport written to: {report_path}")
    print(f"Run ID: {run_id}")
    print(f"Total API calls this run: {tracker.total} / {pipeline.run_config.max_total_api_calls} "
          f"(by role: {tracker.by_role})")
    print(f"LLM Analyst calls used: {pipeline.analyst.llm_calls_made} / {pipeline.run_config.max_analysis_llm_calls}")
    print(f"Exact duplicates rejected: {pipeline.orchestrator.exact_duplicates_avoided}  |  "
          f"Near-duplicates penalized: {pipeline.orchestrator.near_duplicates_penalized}")
    print("\nStrategy performance (RL policy state):")
    for stats in sorted(pipeline.knowledge_base.all_strategy_stats(),
                         key=lambda s: s.avg_reward, reverse=True):
        print(f"  {stats.strategy:32s} attempts={stats.attempts:3d}  "
              f"successes={stats.successes:3d}  avg={stats.avg_reward:+.2f}  "
              f"best={stats.best_reward:+.2f}  recent={stats.recent_avg_reward:+.2f}  "
              f"streak={stats.consecutive_failures}")

    pipeline.knowledge_base.close()


if __name__ == "__main__":
    main()
