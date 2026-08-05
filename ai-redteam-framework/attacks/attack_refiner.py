"""
attacks/attack_refiner.py

Implements the "Learn -> Refine" step of the loop. Looks at Memory
(everything tried so far) and proposes the next generation of attacks by:

1. Prioritizing prompts that were CLOSE to succeeding (rule-based judge
   gave them a nonzero-but-below-threshold score, or an LLM judge marked
   them medium/low severity) — these are the most promising to mutate.
2. Skipping prompts that already succeeded at CRITICAL severity (no need
   to spend more budget confirming something already proven) unless you
   want broader coverage — this default favors coverage over depth.
3. Applying deterministic mutation strategies (attacks/strategies.py) to
   generate variants, and de-duplicating against Memory before returning.

LLM CALL: none by default. Refinement is deterministic mutation +
prioritization logic. (A future LLMAttackRefiner could subclass this to
ask an LLM to propose mutations, but that is intentionally NOT the
default given the project's tight API budget.)
"""

from __future__ import annotations

from attacks import strategies
from core.interfaces import AttackRefiner
from core.types import AttackPrompt, AttackRecord, ObjectiveProfile, Severity


class MutationAttackRefiner(AttackRefiner):
    def __init__(self, max_generation: int = 4):
        # Caps how many times a lineage can be re-mutated, so the queue
        # can't grow unbounded chasing a prompt that will never succeed.
        self.max_generation = max_generation

    def refine(
        self,
        history: list[AttackRecord],
        objective: ObjectiveProfile,
        n: int,
    ) -> list[AttackPrompt]:
        candidates = self._rank_candidates(history)
        seen_hashes = {r.attack.content_hash() for r in history}

        new_prompts: list[AttackPrompt] = []
        for record in candidates:
            if len(new_prompts) >= n:
                break
            if record.attack.generation >= self.max_generation:
                continue

            variants = strategies.mutate_many(record.attack.text, n=2)
            for variant_text in variants:
                if len(new_prompts) >= n:
                    break
                candidate = AttackPrompt(
                    text=variant_text,
                    category=record.attack.category,
                    technique=f"refined:{record.attack.technique}",
                    source="refiner",
                    parent_id=record.attack.id,
                    generation=record.attack.generation + 1,
                )
                if candidate.content_hash() in seen_hashes:
                    continue
                seen_hashes.add(candidate.content_hash())
                new_prompts.append(candidate)

        return new_prompts

    @staticmethod
    def _rank_candidates(history: list[AttackRecord]) -> list[AttackRecord]:
        """Highest-value records to mutate first: near-misses > confirmed
        low/medium severity findings > everything else. Confirmed CRITICAL
        findings are deprioritized (already proven) but not excluded."""

        def score(record: AttackRecord) -> float:
            v = record.verdict
            if v.severity == Severity.CRITICAL:
                return 0.2  # already proven, low priority to re-mutate
            if v.vulnerable:
                return 0.9  # confirmed but not critical — push further
            if 0.0 < v.confidence < 0.75:
                return 0.7  # near-miss / ambiguous — promising to mutate
            return 0.1  # clean refusal, low value to keep mutating

        return sorted(history, key=score, reverse=True)


# ---------------------------------------------------------------------------
# KnowledgeGuidedAttackRefiner — the Attack Refiner for the autonomous
# learning loop. Per the updated architecture, refinement is no longer
# "mutate the last batch"; it's "ask the Strategy Planner which strategy
# to explore next, then ask the Prompt Generator to produce a prompt for
# it, both grounded in the Attack Knowledge Base". This class is a thin
# composition wrapper so the Orchestrator has one call
# (`propose_next(objective)`) regardless of which planner/generator
# implementations are wired in underneath.
#
# Does NOT implement the legacy `AttackRefiner` ABC above — that
# interface's batch `refine(history, objective, n)` signature doesn't fit
# a per-iteration continuous loop. This class is used directly by the new
# Orchestrator instead.
#
# LLM CALL: none, as long as the default TemplatePromptGenerator is used
# (see attacks/prompt_generator.py for the optional LLM-backed variant).
# ---------------------------------------------------------------------------

from core.interfaces import PromptGenerator, StrategyPlanner  # noqa: E402
from core.types import AttackPrompt, ObjectiveProfile  # noqa: E402


class KnowledgeGuidedAttackRefiner:
    def __init__(self, strategy_planner: StrategyPlanner, prompt_generator: PromptGenerator):
        self.strategy_planner = strategy_planner
        self.prompt_generator = prompt_generator

    def propose_next(self, objective: ObjectiveProfile) -> AttackPrompt:
        strategy = self.strategy_planner.select_next(objective)
        return self.prompt_generator.generate(strategy, objective)
