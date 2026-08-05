"""
attacks/strategy_planner.py

Decides WHICH prompt injection strategy to try next. Never generates a
prompt itself — that's attacks/prompt_generator.py's job.

Wraps the Attack Knowledge Base (state) and an EpsilonGreedyPolicy
(selection rule) so the rest of the framework can just call
`select_next(objective)` and get back one of PROMPT_INJECTION_STRATEGIES.

LLM CALL: none. Deterministic given the KB's current stats + the RNG
seed of the underlying policy (the RNG itself is the only source of
randomness, used only for exploration / tie-breaking — never for
"which strategy is best", which is always read from the KB).
"""

from __future__ import annotations

from core.interfaces import StrategyPlanner as StrategyPlannerInterface
from core.types import PROMPT_INJECTION_STRATEGIES, ObjectiveProfile
from knowledge_base.attack_knowledge_base import SQLiteAttackKnowledgeBase
from attacks.policy import EpsilonGreedyPolicy


class BanditStrategyPlanner(StrategyPlannerInterface):
    def __init__(
        self,
        knowledge_base: SQLiteAttackKnowledgeBase,
        policy: EpsilonGreedyPolicy,
        strategies: list[str] | None = None,
    ):
        self.kb = knowledge_base
        self.policy = policy
        self.strategies = strategies or list(PROMPT_INJECTION_STRATEGIES)

    def select_next(self, objective: ObjectiveProfile) -> str:
        stats = {s: self.kb.get_strategy_stats(s) for s in self.strategies}
        return self.policy.select(stats)
