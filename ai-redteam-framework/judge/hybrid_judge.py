"""
judge/hybrid_judge.py

Implements the required flow:

    Rule-Based Judge
        |
        v
    confident? --yes--> return result
        |
        no
        v
    LLM Judge --> return result

This is the ONLY judge the Orchestrator should be given directly. It also
enforces a hard cap (`max_llm_calls`) so a run can never blow past a
budget regardless of how many ambiguous responses show up — once the cap
is hit, ambiguous cases fall back to the rule-based verdict (with its
lower confidence preserved, so it's visible in the report).

LLM CALL: only when RuleBasedJudge's confidence < threshold AND the LLM
call budget has not been exhausted.
"""

from __future__ import annotations

import logging

from core.interfaces import Judge
from core.types import AttackPrompt, JudgeResult, ObjectiveProfile, TargetResponse, VerdictSource
from judge.llm_judge import LLMJudge
from judge.rule_based_judge import RuleBasedJudge

logger = logging.getLogger("redteam.judge.hybrid")


class HybridJudge(Judge):
    def __init__(
        self,
        rule_based: RuleBasedJudge,
        llm_judge: LLMJudge,
        confidence_threshold: float = 0.75,
        max_llm_calls: int = 15,
    ):
        self.rule_based = rule_based
        self.llm_judge = llm_judge
        self.confidence_threshold = confidence_threshold
        self.max_llm_calls = max_llm_calls
        self._llm_calls_made = 0

    def evaluate(
        self,
        attack: AttackPrompt,
        response: TargetResponse,
        objective: ObjectiveProfile,
    ) -> JudgeResult:
        rule_result = self.rule_based.evaluate(attack, response, objective)

        if rule_result.confidence >= self.confidence_threshold:
            return rule_result

        if self._llm_calls_made >= self.max_llm_calls:
            logger.warning(
                "LLM judge call budget (%d) exhausted; keeping rule-based "
                "verdict despite low confidence (%.2f).",
                self.max_llm_calls,
                rule_result.confidence,
            )
            return rule_result

        self._llm_calls_made += 1
        llm_result = self.llm_judge.evaluate(attack, response, objective)
        llm_result.source = VerdictSource.HYBRID
        logger.debug(
            "Escalated to LLM judge (%d/%d calls used). rule_confidence=%.2f",
            self._llm_calls_made,
            self.max_llm_calls,
            rule_result.confidence,
        )
        return llm_result

    @property
    def llm_calls_made(self) -> int:
        return self._llm_calls_made
