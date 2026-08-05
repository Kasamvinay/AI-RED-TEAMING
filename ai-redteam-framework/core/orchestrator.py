"""
core/orchestrator.py

Drives the iterative loop described in the architecture:

    Attack Generator -> Target Adapter -> Judge -> Memory -> Attack Refiner -> repeat

This module contains no provider-specific code and no LLM calls itself —
it only calls the interfaces defined in core/interfaces.py. Swapping any
component (adapter, judge, generator, refiner, report generator) requires
zero changes here.
"""

from __future__ import annotations

import logging
import uuid

from core.interfaces import (
    AttackGenerator,
    AttackRefiner,
    Judge,
    MemoryStore,
    ReportGenerator,
    TargetSystemAdapter,
)
from core.types import AttackRecord, RunConfig, Severity

logger = logging.getLogger("redteam.orchestrator")


class Orchestrator:
    """Coordinates one full red-team run against a target system."""

    def __init__(
        self,
        adapter: TargetSystemAdapter,
        judge: Judge,
        generator: AttackGenerator,
        refiner: AttackRefiner,
        memory: MemoryStore,
        report_generator: ReportGenerator,
        config: RunConfig,
    ):
        self.adapter = adapter
        self.judge = judge
        self.generator = generator
        self.refiner = refiner
        self.memory = memory
        self.report_generator = report_generator
        self.config = config

    def run(self, run_name: str = "redteam_run") -> str:
        """
        Executes the full loop and returns the filepath of the generated
        vulnerability report.
        """
        objective = self.config.objective
        logger.info("Starting red-team run '%s' against objective '%s'",
                    run_name, objective.name)

        # --- Seed generation: benchmarks + autonomous generator ---
        seed_attacks = []
        if self.config.autonomous_generation:
            seed_attacks.extend(
                self.generator.generate(objective, n=self.config.max_iterations)
            )

        attacks_this_round = seed_attacks[: self.config.max_iterations]
        iteration = 0

        while attacks_this_round and iteration < self.config.max_iterations:
            attack = attacks_this_round.pop(0)
            iteration += 1

            content_hash = attack.content_hash()
            if self.memory.seen_hash(content_hash):
                logger.debug("Skipping duplicate prompt (iteration %d)", iteration)
                continue

            response = self.adapter.send(attack)

            cached = self.memory.get_cached_verdict(content_hash)
            if cached is not None:
                verdict = cached
            else:
                verdict = self.judge.evaluate(attack, response, objective)

            record = AttackRecord(attack=attack, response=response, verdict=verdict)
            self.memory.add(record)

            logger.info(
                "[%d/%d] category=%s vulnerable=%s severity=%s source=%s",
                iteration,
                self.config.max_iterations,
                attack.category,
                verdict.vulnerable,
                verdict.severity.value,
                verdict.source.value,
            )

            if verdict.vulnerable and self.config.stop_on_critical \
                    and verdict.severity == Severity.CRITICAL:
                logger.warning("Critical vulnerability found — stopping early.")
                break

            # Refill the queue by refining once the current batch runs low.
            if not attacks_this_round and iteration < self.config.max_iterations:
                remaining = self.config.max_iterations - iteration
                new_batch = self.refiner.refine(
                    self.memory.all_records(),
                    objective,
                    n=min(self.config.refine_top_n, remaining),
                )
                attacks_this_round.extend(new_batch)

        report_path = self.report_generator.generate(
            self.memory.all_records(), run_name=run_name
        )
        logger.info("Run complete. Report written to %s", report_path)
        return report_path


# ---------------------------------------------------------------------------
# AutonomousOrchestrator — drives the new continuous learning loop:
#
#   Attack Knowledge Base -> Strategy Planner -> Prompt Generator
#   -> Target System Adapter -> Target AI System -> Attack Analyst
#   -> Experience Memory -> (KB.record_experience = RL policy update)
#   -> back to Attack Knowledge Base
#
# Unlike the legacy Orchestrator above (which pre-generates a batch, then
# refines in batches), this loop is per-iteration: every single attack's
# outcome immediately updates the Knowledge Base before the next
# strategy is chosen. That's what makes it "autonomous learning" rather
# than "generate once, judge, refine in bulk".
# ---------------------------------------------------------------------------

from attacks.attack_refiner import KnowledgeGuidedAttackRefiner  # noqa: E402
from attacks.reward import RewardConfig, compute_reward  # noqa: E402
from core.interfaces import AttackAnalyst, ExperienceMemory, TargetSystemAdapter  # noqa: E402
from core.types import AttackExperience  # noqa: E402
from knowledge_base.attack_knowledge_base import SQLiteAttackKnowledgeBase  # noqa: E402
from reporting.experience_report_generator import ExperienceReportGenerator  # noqa: E402


class AutonomousOrchestrator:
    def __init__(
        self,
        adapter: TargetSystemAdapter,
        knowledge_base: SQLiteAttackKnowledgeBase,
        refiner: KnowledgeGuidedAttackRefiner,
        analyst: AttackAnalyst,
        experience_memory: ExperienceMemory,
        report_generator: ExperienceReportGenerator,
        config: RunConfig,
        reward_config: RewardConfig | None = None,
        api_call_tracker=None,
        on_event=None,
    ):
        self.adapter = adapter
        self.kb = knowledge_base
        self.refiner = refiner
        self.analyst = analyst
        self.experience_memory = experience_memory
        self.report_generator = report_generator
        self.config = config
        self.reward_config = reward_config or RewardConfig()
        self.api_call_tracker = api_call_tracker
        self.exact_duplicates_avoided = 0
        self.near_duplicates_penalized = 0
        # Optional callback: on_event(event: str, **fields) -> None. Called
        # at each pipeline stage of every iteration (strategy_selected,
        # prompt_generated, attack_sent, response_received, judge_completed,
        # knowledge_updated) plus once for report_generated. Purely additive
        # instrumentation — the CLI pipeline (main.py) never passes one, so
        # its behavior is byte-for-byte unchanged. The API layer (api/) uses
        # this to drive GET /status without touching the loop itself.
        self._on_event = on_event or (lambda event, **fields: None)

    def run(self, run_name: str = "prompt_injection_run", run_id: str = "") -> str:
        run_id = run_id or uuid.uuid4().hex[:12]
        objective = self.config.objective
        logger.info(
            "Starting autonomous prompt-injection run '%s' (%s) against objective '%s'",
            run_name, run_id, objective.name,
        )

        iteration = 0
        attempts = 0
        max_attempts = self.config.max_iterations * 3  # guard against dedup starving the loop

        while iteration < self.config.max_iterations and attempts < max_attempts:
            if self.api_call_tracker is not None and \
                    self.api_call_tracker.exceeded(self.config.max_total_api_calls):
                logger.warning(
                    "Global API call budget (%d) exhausted after %d calls — stopping run early.",
                    self.config.max_total_api_calls, self.api_call_tracker.total,
                )
                break

            attempts += 1
            prompt = self.refiner.propose_next(objective)
            strategy_preview = prompt.metadata.get("strategy", prompt.technique.split("#")[0])
            self._on_event("strategy_selected", iteration=iteration + 1,
                            max_iterations=self.config.max_iterations, strategy=strategy_preview)
            self._on_event("prompt_generated", iteration=iteration + 1,
                            strategy=strategy_preview, prompt_preview=prompt.text[:200])

            content_hash = prompt.content_hash()
            if self.kb.seen_prompt_hash(content_hash):
                # Exact duplicate: reject outright, don't spend a target
                # call or an iteration slot on it.
                self.exact_duplicates_avoided += 1
                logger.debug("Skipping exact-duplicate prompt (attempt %d)", attempts)
                continue

            iteration += 1
            strategy = prompt.metadata.get("strategy", prompt.technique.split("#")[0])

            is_near_dup = self.kb.is_near_duplicate(
                strategy, prompt.text, self.config.near_duplicate_threshold
            )
            if is_near_dup:
                self.near_duplicates_penalized += 1

            self._on_event("attack_sent", iteration=iteration, strategy=strategy)
            turns = prompt.metadata.get("turns")
            if turns and self.config.multi_turn_enabled:
                response = self.adapter.send_conversation(turns[: self.config.multi_turn_max_turns])
            else:
                response = self.adapter.send(prompt)
            self._on_event("response_received", iteration=iteration, strategy=strategy,
                            response_preview=(response.text or "")[:200], error=response.error)

            analysis = self.analyst.analyze(prompt, response, objective)
            self._on_event("judge_completed", iteration=iteration, strategy=strategy,
                            outcome=analysis.outcome, score=analysis.score,
                            severity=analysis.severity.value)

            stats_before = self.kb.get_strategy_stats(strategy)
            strategy_had_no_success_yet = stats_before.successes == 0
            reward = compute_reward(
                analysis,
                is_duplicate=False,  # exact duplicates are rejected above, never scored
                is_near_duplicate=is_near_dup,
                is_first_success_for_strategy=strategy_had_no_success_yet,
                consecutive_failures_before_this_attempt=stats_before.consecutive_failures,
                config=self.reward_config,
            )

            experience = AttackExperience(
                strategy=strategy,
                prompt=prompt,
                response=response,
                analysis=analysis,
                reward=reward,
                run_id=run_id,
            )

            # This call IS the RL policy update — see attack_knowledge_base.py.
            self.kb.record_experience(experience)
            self.experience_memory.add(experience)
            self._on_event("knowledge_updated", iteration=iteration, strategy=strategy,
                            reward=reward, total_attempts_this_strategy=stats_before.attempts + 1)

            logger.info(
                "[%d/%d] strategy=%s outcome=%s score=%.2f reward=%.2f "
                "novelty=%.2f behavior_changed=%s source=%s api_calls=%s",
                iteration, self.config.max_iterations,
                strategy, analysis.outcome, analysis.score, reward,
                analysis.novelty, analysis.behavior_changed, analysis.source.value,
                self.api_call_tracker.total if self.api_call_tracker else "n/a",
            )

            if analysis.outcome == "success" and self.config.stop_on_critical \
                    and analysis.severity == Severity.CRITICAL:
                logger.warning("Critical prompt injection found — stopping early.")
                break

        run_stats = {
            "exact_duplicates_avoided": self.exact_duplicates_avoided,
            "near_duplicates_penalized": self.near_duplicates_penalized,
            "total_api_calls": self.api_call_tracker.total if self.api_call_tracker else None,
            "api_calls_by_role": self.api_call_tracker.by_role if self.api_call_tracker else None,
            "source_breakdown": self.kb.source_breakdown(),
        }

        run_experiences = self.experience_memory.get_run_experiences(run_id)

        report_path = self.report_generator.generate(
            run_experiences,
            self.kb.all_strategy_stats(),
            run_name=run_name,
            run_stats=run_stats,
        )
        self._on_event("report_generated", report_path=report_path)
        logger.info("Run complete. Report written to %s", report_path)
        return report_path
