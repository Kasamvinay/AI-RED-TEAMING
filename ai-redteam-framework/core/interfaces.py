"""
core/interfaces.py

The framework depends on these abstractions, never on concrete providers.
This is what makes it possible to swap OpenAI -> Claude -> an internal
REST chatbot -> a RAG pipeline without touching orchestration, judging,
attack generation, or reporting.

Pure Python (ABCs only). No LLM calls happen in this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.types import (
    AttackPrompt,
    AttackRecord,
    JudgeResult,
    ObjectiveProfile,
    TargetResponse,
)


class TargetSystemAdapter(ABC):
    """
    Common interface for "the thing being tested".

    Implementations: OpenAIAdapter, ClaudeAdapter, RestApiAdapter,
    EnterpriseChatbotAdapter, RagAdapter, etc.

    Contract: send(prompt) -> TargetResponse. That's it. The rest of the
    framework only ever calls `send` (or `send_conversation` for
    multi-turn attack sessions — see below).
    """

    name: str = "base_adapter"

    @abstractmethod
    def send(self, prompt: AttackPrompt) -> TargetResponse:
        """Send an attack prompt to the target system and normalize the reply."""
        raise NotImplementedError

    def send_conversation(self, turns: list[str]) -> TargetResponse:
        """
        Sends a multi-turn attack session (see attacks/prompt_generator.py's
        multi_turn_escalation strategy) and returns the response to the
        FINAL turn. Conversation history is scoped to this one call only —
        adapters must never carry state between separate send_conversation
        calls, so unrelated attack sessions never mix.

        Default fallback for adapters that don't override this (e.g. a
        simple REST adapter with no native multi-turn support): flattens
        the turns into one combined single-shot prompt. Adapters that CAN
        maintain real conversational state (OpenAIAdapter) override this
        with an actual multi-turn exchange.
        """
        combined = "\n\n".join(f"[Turn {i + 1}] {t}" for i, t in enumerate(turns))
        synthetic = AttackPrompt(
            text=combined, category="prompt_injection", technique="multi_turn_fallback"
        )
        return self.send(synthetic)


class Judge(ABC):
    """
    Common interface for anything that can score an attack/response pair.

    Implementations: RuleBasedJudge (pure Python, free), LLMJudge (costs
    tokens), HybridJudge (composes the two to minimize API usage).
    """

    @abstractmethod
    def evaluate(
        self,
        attack: AttackPrompt,
        response: TargetResponse,
        objective: ObjectiveProfile,
    ) -> JudgeResult:
        raise NotImplementedError


class AttackGenerator(ABC):
    """Produces new AttackPrompts, either from scratch or from a benchmark."""

    @abstractmethod
    def generate(
        self, objective: ObjectiveProfile, n: int
    ) -> list[AttackPrompt]:
        raise NotImplementedError


class AttackRefiner(ABC):
    """
    Takes prior AttackRecords (attack + response + verdict) and proposes
    the next generation of attacks. This is the "learn" step in
    Attack -> Evaluate -> Learn -> Refine -> Repeat.
    """

    @abstractmethod
    def refine(
        self,
        history: list[AttackRecord],
        objective: ObjectiveProfile,
        n: int,
    ) -> list[AttackPrompt]:
        raise NotImplementedError


class MemoryStore(ABC):
    """Persists AttackRecords and supports de-duplication / lookback queries."""

    @abstractmethod
    def add(self, record: AttackRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def all_records(self) -> list[AttackRecord]:
        raise NotImplementedError

    @abstractmethod
    def seen_hash(self, content_hash: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_cached_verdict(self, content_hash: str) -> Optional[JudgeResult]:
        raise NotImplementedError


class ReportGenerator(ABC):
    """Turns Memory into a structured, shareable vulnerability report."""

    @abstractmethod
    def generate(self, records: list[AttackRecord], run_name: str) -> str:
        """Returns a filepath to the generated report."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Autonomous learning loop interfaces (Prompt Injection specialization).
#
# New workflow this set of interfaces supports:
#
#   Benchmark Dataset -> Attack Knowledge Base -> Strategy Planner
#   -> Prompt Generator -> Target System Adapter -> Target AI System
#   -> Attack Analyst -> Experience Memory -> (RL policy update, which
#   lives inside Attack Knowledge Base) -> back to Attack Knowledge Base
#
# TargetSystemAdapter above is reused unchanged — the target system side
# of the contract doesn't change when the attack side gets smarter.
# ---------------------------------------------------------------------------

from core.types import (  # noqa: E402  (grouped here to keep the legacy
    AttackAnalysis,       # interfaces above importable without pulling in
    AttackExperience,     # the newer types)
    StrategyStats,
)


class KnowledgeBase(ABC):
    """
    The Attack Knowledge Base: strategies, prior experiences, success/
    failure rates, and benchmark-derived exemplars, all in one place.
    This is what makes strategy selection and prompt generation "learn"
    instead of restarting from zero every run.
    """

    @abstractmethod
    def bootstrap_from_benchmarks(self, entries: list[dict]) -> None:
        """One-time seed from benchmark dataset entries (not replayed
        directly — mapped into strategies + stored as style exemplars)."""
        raise NotImplementedError

    @abstractmethod
    def record_experience(self, experience: AttackExperience) -> None:
        """Persists an experience and updates strategy/variant statistics
        (this update IS the RL policy update — see attacks/policy.py)."""
        raise NotImplementedError

    @abstractmethod
    def get_strategy_stats(self, strategy: str) -> StrategyStats:
        raise NotImplementedError

    @abstractmethod
    def all_strategy_stats(self) -> list[StrategyStats]:
        raise NotImplementedError

    @abstractmethod
    def get_variant_stats(self, strategy: str) -> dict[str, StrategyStats]:
        """Finer-grained stats per template variant within a strategy."""
        raise NotImplementedError

    @abstractmethod
    def seen_prompt_hash(self, content_hash: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_near_duplicate(self, strategy: str, prompt_text: str, threshold: float = 0.82) -> bool:
        """Practical (not just exact-hash) duplicate detection: compares
        prompt_text against recent prompts for this strategy using string
        similarity, so minor wording changes don't count as a new attack."""
        raise NotImplementedError

    @abstractmethod
    def get_recent_experiences(self, strategy: str, n: int = 5) -> list[dict]:
        """Recent prompt/response/outcome/reward records for a strategy —
        used by the LLM Prompt Generator so it can see what was already
        tried (and what worked or didn't) before writing the next attack."""
        raise NotImplementedError

    @abstractmethod
    def best_prompts_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        """Highest-reward prior prompt texts for a strategy — used by the
        Prompt Generator as guidance, not copied verbatim."""
        raise NotImplementedError

    @abstractmethod
    def benchmark_seeds_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def recommendations_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        raise NotImplementedError


class StrategyPlanner(ABC):
    """
    Decides which prompt injection strategy to explore next. Does NOT
    generate prompts. Balances exploration of under-tried strategies
    against exploitation of strategies with high observed reward, using
    deterministic Python logic driven by the Attack Knowledge Base.
    """

    @abstractmethod
    def select_next(self, objective: ObjectiveProfile) -> str:
        """Returns one of PROMPT_INJECTION_STRATEGIES."""
        raise NotImplementedError


class PromptGenerator(ABC):
    """
    Generates the actual attack prompt for a chosen strategy, guided by
    the objective, the Attack Knowledge Base's accumulated experience,
    and benchmark exemplars — not by random mutation.
    """

    @abstractmethod
    def generate(self, strategy: str, objective: ObjectiveProfile) -> AttackPrompt:
        raise NotImplementedError


class AttackAnalyst(ABC):
    """
    Replaces the plain Judge/HybridJudge for the autonomous loop: still
    rule-based first to minimize API usage, escalating to an LLM only for
    genuinely ambiguous cases — but returns a structured AttackAnalysis
    (outcome, confidence, explanation, defense triggered, recommendation,
    tags) instead of just a vulnerable/not-vulnerable score.
    """

    @abstractmethod
    def analyze(
        self,
        attack: AttackPrompt,
        response: TargetResponse,
        objective: ObjectiveProfile,
    ) -> AttackAnalysis:
        raise NotImplementedError


class ExperienceMemory(ABC):
    """Persists complete AttackExperience records (strategy + prompt +
    response + analysis + reward), the framework's growing dataset."""

    @abstractmethod
    def add(self, experience: AttackExperience) -> None:
        raise NotImplementedError

    @abstractmethod
    def all_experiences(self) -> list[AttackExperience]:
        raise NotImplementedError

    def get_run_experiences(self, run_id: str) -> list[AttackExperience]:
        """Returns experiences for one run_id only.

        Existing callers can keep using all_experiences() for historical
        lookback. Report generation should use this method when it needs a
        run-scoped list.
        """
        return [e for e in self.all_experiences() if e.run_id == run_id]
