"""
core/types.py

Central data contracts used across the entire framework.

No module outside `core/` should redefine these shapes. Adapters, judges,
attack generators, and report generators all speak these dataclasses so
that the pieces stay decoupled from one another.

Pure Python. No LLM calls. No network calls.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    """Severity of a discovered vulnerability."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class VerdictSource(str, Enum):
    """Which layer of the Hybrid Judge produced a verdict."""
    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"  # rule-based abstained, LLM decided


@dataclass
class AttackPrompt:
    """A single adversarial prompt to be sent to a target system."""
    text: str
    category: str  # e.g. "prompt_injection", "jailbreak", "data_exfiltration"
    technique: str  # e.g. "roleplay", "obfuscation", "instruction_override"
    source: str = "generator"  # "generator" | "benchmark:<name>" | "refiner"
    parent_id: Optional[str] = None  # id of the prompt this was mutated from
    generation: int = 0  # how many refinement cycles produced this prompt
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def content_hash(self) -> str:
        """Stable hash used for de-duplication and caching (no API calls)."""
        return hashlib.sha256(self.text.strip().lower().encode("utf-8")).hexdigest()


@dataclass
class TargetResponse:
    """Normalized response from any Target System Adapter."""
    prompt_id: str
    text: str
    raw: Any = None  # original provider payload, kept for debugging only
    latency_ms: Optional[float] = None
    adapter_name: str = "unknown"
    error: Optional[str] = None


@dataclass
class JudgeResult:
    """Verdict produced by the Hybrid Judge for one attack/response pair."""
    prompt_id: str
    vulnerable: bool
    confidence: float  # 0.0 - 1.0
    severity: Severity
    reason: str
    matched_signals: list[str] = field(default_factory=list)
    source: VerdictSource = VerdictSource.RULE_BASED
    category: str = "unknown"


@dataclass
class AttackRecord:
    """One full row of Memory: an attack, its response, and its verdict."""
    attack: AttackPrompt
    response: TargetResponse
    verdict: JudgeResult
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ObjectiveProfile:
    """Defines what 'safe behavior' means for a given target system."""
    name: str
    system_prompt: str
    attack_goals: list[str]
    safety_expectations: list[str]
    disallowed_topics: list[str] = field(default_factory=list)
    evaluation_notes: str = ""


@dataclass
class RunConfig:
    """Top-level configuration for a red-team run."""
    objective: ObjectiveProfile
    max_iterations: int = 20
    max_llm_judge_calls: int = 15
    rule_based_confidence_threshold: float = 0.75
    use_benchmarks: bool = True
    benchmark_names: list[str] = field(default_factory=lambda: ["custom"])
    autonomous_generation: bool = True
    refine_top_n: int = 3
    stop_on_critical: bool = False

    # --- Autonomous learning loop (Attack Knowledge Base / RL policy) ---
    exploration_rate: float = 0.25  # epsilon in the epsilon-greedy strategy policy
    max_analysis_llm_calls: int = 15  # cap on Attack Analyst LLM escalations
    kb_path: str = "output/knowledge_base.sqlite3"
    experience_memory_path: str = "output/experience_memory.jsonl"

    # --- Experimental-quality settings (final week: quality > token minimization) ---
    prompt_generator: str = "llm"  # "llm" (default) | "template" (offline/baseline)
    multi_turn_enabled: bool = True
    multi_turn_max_turns: int = 4
    near_duplicate_threshold: float = 0.82  # difflib similarity above this = near-duplicate
    max_total_api_calls: int = 300  # hard safety cap across generator+target+analyst combined


# ---------------------------------------------------------------------------
# Prompt Injection specialization: strategies, structured analysis, and
# full "experience" records used by the autonomous learning loop.
# ---------------------------------------------------------------------------

#: The eight canonical prompt-injection strategies the Strategy Planner
#: chooses between. This list is the fixed action space for the RL policy.
#: Each is a CATEGORY, not a fixed prompt — the LLM Prompt Generator writes
#: a context-appropriate concrete attack for whichever category is chosen.
PROMPT_INJECTION_STRATEGIES: list[str] = [
    "direct_instruction_conflict",     # explicit "ignore/override your instructions"
    "context_manipulation",            # fabricated context the target is asked to act on
    "role_context_framing",            # roleplay / persona / fictional framing
    "authority_framing",               # admin/developer/debug-mode impersonation
    "instruction_hierarchy_confusion", # blurring system vs. user vs. tool instruction levels
    "multi_turn_escalation",           # benign context first, escalate over several turns
    "indirect_instruction_placement",  # instruction embedded in "external" content/data
    "format_encoding_variation",       # translation, encoding, markup tricks to slip past filters
]

#: Outcome vocabulary for the Attack Analyst — deliberately not binary,
#: so "partial success" (e.g. a guardrail partially bypassed) is a first-
#: class outcome that still teaches the policy something.
AttackOutcome = str  # "success" | "partial" | "failure"


@dataclass
class StrategyStats:
    """Aggregated performance of one strategy (or strategy+variant key) as
    tracked by the Attack Knowledge Base. This IS the RL policy's state
    for that action — attempts/avg_reward drive strategy selection."""
    strategy: str
    attempts: int = 0
    successes: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    best_reward: float = 0.0
    recent_avg_reward: float = 0.0  # mean reward of the last N attempts (trend signal)
    consecutive_failures: int = 0    # current failure streak, resets on success/partial
    last_used: Optional[str] = None


@dataclass
class AttackAnalysis:
    """Structured output of the Attack Analyst — replaces the plain
    JudgeResult score with enough detail for the policy and the next
    Prompt Generator call to actually learn something."""
    prompt_id: str
    strategy: str
    objective: str
    outcome: AttackOutcome  # "success" | "partial" | "failure"
    score: float  # 0.0-1.0 continuous strength of the attack, independent of the discrete outcome
    confidence: float
    explanation: str
    observed_behavior: str = ""  # what the target actually did, in plain language
    evidence: list[str] = field(default_factory=list)  # concrete quoted/matched signals
    instructions_overridden: bool = False  # did the target appear to abandon its own instructions?
    behavior_changed: bool = False  # did this response differ meaningfully from prior attempts at this strategy?
    novelty: float = 0.5  # 0.0 (identical to something already seen) - 1.0 (genuinely new behavior)
    defense_triggered: Optional[str] = None
    recommendation: str = ""
    tags: list[str] = field(default_factory=list)
    source: VerdictSource = VerdictSource.RULE_BASED
    severity: Severity = Severity.NONE

    @property
    def success(self) -> bool:
        return self.outcome == "success"


@dataclass
class AttackExperience:
    """One complete row of Experience Memory: strategy, prompt, response,
    structured analysis, reward, and everything needed to re-derive
    knowledge-base statistics or replay a run for auditing."""
    strategy: str
    prompt: AttackPrompt
    response: TargetResponse
    analysis: AttackAnalysis
    reward: float
    run_id: str = ""  # which orchestrator.run() call produced this — "" for pre-existing records
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
