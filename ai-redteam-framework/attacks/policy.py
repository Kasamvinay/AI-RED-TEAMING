"""
attacks/policy.py

The reinforcement-learning piece, scoped deliberately small: a multi-armed
bandit (epsilon-greedy with forced initial exploration) rather than a full
deep-RL stack. This is a genuine, standard RL formulation — just a
single-state one, which is the right amount of machinery for "which of
the 8 strategies should I try next".

Formulation
-----------
State:   the accumulated StrategyStats for every strategy (and variant)
         in the Attack Knowledge Base — attempts, successes, avg_reward,
         best_reward, recent_avg_reward (trend), consecutive_failures.
         There's a single implicit state (this is a stationary bandit,
         not a multi-state MDP), so "state" really means "everything the
         policy currently knows", which is exactly what the KB holds.
Action:  choose one strategy (or, at the finer grain, one template
         variant within a chosen strategy) to try next.
Reward:  a float in [-1, 1] computed by attacks/reward.py from the Attack
         Analyst's structured analysis.
Policy:  epsilon-greedy over a COMBINED score (not just raw avg_reward):

             combined = 0.5 * avg_reward
                      + 0.3 * recent_avg_reward   (is it working *lately*?)
                      + 0.2 * best_reward         (has it ever hit something good?)
                      - failure_streak_penalty    (discourage flogging a dead strategy)

         with cold-start forcing (every action gets one free try before
         exploitation kicks in) and standard epsilon exploration on top.

"Policy update" has no separate step here — it's implicit: the Knowledge
Base's `record_experience()` updates avg_reward/best_reward/recent_avg_reward,
and the next call to `select()` reads the updated numbers straight back
out. No weights file, no gradient step — just incrementally-tracked
statistics per action.

LLM CALL: none. Pure Python.
"""

from __future__ import annotations

import random
from typing import Optional

from core.types import StrategyStats

# Weights for the combined score. Kept as module-level constants (not a
# config knob) because they encode a design choice about what "good"
# means, not something a user should casually retune per run.
_AVG_REWARD_WEIGHT = 0.5
_RECENT_REWARD_WEIGHT = 0.3
_BEST_REWARD_WEIGHT = 0.2
_FAILURE_STREAK_PENALTY_PER_STEP = 0.08
_MAX_FAILURE_STREAK_PENALTY = 0.4
#: A strategy needs at least this many attempts before it's considered
#: "sufficiently explored" for the failure-streak penalty to kick in —
#: otherwise a single early failure would unfairly tank a fresh strategy.
_MIN_ATTEMPTS_BEFORE_STREAK_PENALTY = 2


def combined_score(stats: StrategyStats) -> float:
    """The value the policy actually ranks actions by — see module
    docstring for the formulation. Exposed as a standalone function so the
    Strategy Planner and reporting can both use the exact same notion of
    'how good does this strategy look right now'."""
    score = (
        _AVG_REWARD_WEIGHT * stats.avg_reward
        + _RECENT_REWARD_WEIGHT * stats.recent_avg_reward
        + _BEST_REWARD_WEIGHT * stats.best_reward
    )
    if stats.attempts >= _MIN_ATTEMPTS_BEFORE_STREAK_PENALTY:
        penalty = min(
            stats.consecutive_failures * _FAILURE_STREAK_PENALTY_PER_STEP,
            _MAX_FAILURE_STREAK_PENALTY,
        )
        score -= penalty
    return score


class EpsilonGreedyPolicy:
    def __init__(self, exploration_rate: float = 0.25, rng: Optional[random.Random] = None):
        self.exploration_rate = exploration_rate
        self._rng = rng or random.Random()

    def select(self, stats_by_action: dict[str, StrategyStats]) -> str:
        """Given {action_key: StrategyStats}, returns the chosen action key."""
        actions = list(stats_by_action.keys())
        if not actions:
            raise ValueError("select() called with no candidate actions")

        # Cold start: always try an untested action first.
        untried = [a for a in actions if stats_by_action[a].attempts == 0]
        if untried:
            return self._rng.choice(untried)

        # Exploration.
        if self._rng.random() < self.exploration_rate:
            return self._rng.choice(actions)

        # Exploitation: highest combined score, ties broken randomly.
        scores = {a: combined_score(stats_by_action[a]) for a in actions}
        best_score = max(scores.values())
        best_actions = [a for a in actions if scores[a] == best_score]
        return self._rng.choice(best_actions)
