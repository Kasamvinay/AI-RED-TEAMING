"""
knowledge_base/attack_knowledge_base.py

The Attack Knowledge Base is the framework's persistent, evolving memory
of "what works". It answers:

- Which strategies have we tried, how often, and how well (avg / best /
  recent-trend reward, current failure streak)?
- Which template *variant* within a strategy performs best?
- What benchmark-derived examples exist for a given strategy?
- What recommendations has the Attack Analyst made for this strategy?
- Have we already sent this exact prompt before — or something close
  enough in wording to count as the same attack (practical/semantic
  duplicate detection, not just exact-hash)?
- What did we try recently for this strategy, and how did it go? (used
  by the LLM Prompt Generator so it writes something genuinely new)

Storage: SQLite (stdlib `sqlite3`, zero extra dependencies). This is the
"simple and extensible" implementation called for — swapping in Postgres
or a vector store later only means rewriting this one file.

IMPORTANT — this is also where "RL policy update" lives. There is no
separate policy-weights file: `record_experience()` updates each
strategy/variant's (attempts, successes, total_reward, avg_reward,
best_reward, recent_avg_reward, consecutive_failures). The policy in
attacks/policy.py reads those numbers back out on every selection call.
Knowledge Base update == policy update.

LLM CALL: none. Pure Python + SQL + stdlib difflib for similarity.
"""

from __future__ import annotations

import difflib
import json
import sqlite3
from typing import Optional

from core.interfaces import KnowledgeBase
from core.types import (
    PROMPT_INJECTION_STRATEGIES,
    AttackExperience,
    StrategyStats,
)

# Maps benchmark dataset `technique` labels (see benchmarks/datasets/*.json)
# onto the eight canonical strategies. Anything unrecognized falls back to
# "direct_instruction_conflict" so bootstrap never silently drops an entry.
_TECHNIQUE_TO_STRATEGY = {
    "instruction_override": "direct_instruction_conflict",
    "direct_ask": "direct_instruction_conflict",
    "developer_pretext": "authority_framing",
    "mode_override": "authority_framing",
    "authority_injection": "authority_framing",
    "impersonation_request": "authority_framing",
    "roleplay": "role_context_framing",
    "persona_injection": "role_context_framing",
    "fictional_framing": "role_context_framing",
    "social_engineering": "context_manipulation",
    "step_by_step_bait": "context_manipulation",
    "translation_wrapper": "format_encoding_variation",
}

# Recent-trend window: how many of the most recent attempts for a
# strategy count toward `recent_avg_reward` (a signal the policy uses to
# tell "this strategy is currently improving/declining" apart from its
# all-time average).
_RECENT_WINDOW = 5

# How many recent prompts per strategy to compare against for practical
# duplicate detection. Bounded so the similarity check stays cheap even
# after a long run.
_DUPLICATE_CHECK_WINDOW = 25


def map_technique_to_strategy(technique: str) -> str:
    return _TECHNIQUE_TO_STRATEGY.get(technique, "direct_instruction_conflict")


class SQLiteAttackKnowledgeBase(KnowledgeBase):
    def __init__(self, path: str = "output/knowledge_base.sqlite3",
                 strategies: Optional[list[str]] = None):
        self.path = path
        self.strategies = strategies or list(PROMPT_INJECTION_STRATEGIES)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._migrate_schema()
        self._seed_strategies()

    # -- schema -------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_stats (
                key TEXT PRIMARY KEY,        -- strategy, or "strategy#variant"
                strategy TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                successes INTEGER NOT NULL DEFAULT 0,
                total_reward REAL NOT NULL DEFAULT 0.0,
                avg_reward REAL NOT NULL DEFAULT 0.0,
                best_reward REAL NOT NULL DEFAULT 0.0,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_used TEXT
            );

            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                strategy TEXT NOT NULL,
                variant TEXT,
                prompt_text TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                response_text TEXT,
                outcome TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0.0,
                confidence REAL NOT NULL,
                reward REAL NOT NULL,
                explanation TEXT,
                recommendation TEXT,
                tags TEXT,                   -- JSON list
                source TEXT,                 -- "strategy_planner" | "strategy_planner:llm" | "benchmark:<name>"
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_experiences_hash
                ON experiences(prompt_hash);
            CREATE INDEX IF NOT EXISTS idx_experiences_strategy
                ON experiences(strategy);

            CREATE TABLE IF NOT EXISTS benchmark_seeds (
                strategy TEXT NOT NULL,
                example_prompt TEXT NOT NULL,
                dataset TEXT
            );
            """
        )
        self._conn.commit()

    def _migrate_schema(self) -> None:
        """Best-effort ALTER TABLE for knowledge bases created by an
        earlier version of this framework (before best_reward /
        consecutive_failures / score / source columns existed). Safe to
        run every startup — each ALTER is a no-op if the column already
        exists."""
        migrations = [
            "ALTER TABLE strategy_stats ADD COLUMN best_reward REAL NOT NULL DEFAULT 0.0",
            "ALTER TABLE strategy_stats ADD COLUMN consecutive_failures INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE experiences ADD COLUMN score REAL NOT NULL DEFAULT 0.0",
            "ALTER TABLE experiences ADD COLUMN source TEXT",
        ]
        for stmt in migrations:
            try:
                self._conn.execute(stmt)
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

    def _seed_strategies(self) -> None:
        for strategy in self.strategies:
            self._conn.execute(
                "INSERT OR IGNORE INTO strategy_stats (key, strategy) VALUES (?, ?)",
                (strategy, strategy),
            )
        self._conn.commit()

    # -- bootstrap ------------------------------------------------------

    def bootstrap_from_benchmarks(self, entries: list[dict]) -> None:
        """Extracts strategy exemplars from benchmark entries. Does NOT
        touch strategy_stats (rewards stay unbiased / zero until the
        framework earns them through real attacks) — only populates
        benchmark_seeds, which the Prompt Generator draws style/knowledge
        from. The benchmark set itself is never replayed directly."""
        rows = []
        for entry in entries:
            technique = entry.get("technique", "")
            strategy = map_technique_to_strategy(technique)
            rows.append((strategy, entry["prompt"], entry.get("dataset", "unknown")))
        if rows:
            self._conn.executemany(
                "INSERT INTO benchmark_seeds (strategy, example_prompt, dataset) "
                "VALUES (?, ?, ?)",
                rows,
            )
            self._conn.commit()

    # -- experience / policy update --------------------------------------

    def record_experience(self, experience: AttackExperience) -> None:
        strategy = experience.strategy
        variant = experience.prompt.technique  # e.g. "role_context_framing#1" or "...#llm"
        reward = experience.reward
        outcome = experience.analysis.outcome
        now = experience.timestamp

        self._conn.execute(
            """INSERT INTO experiences
               (id, strategy, variant, prompt_text, prompt_hash, response_text,
                outcome, score, confidence, reward, explanation, recommendation,
                tags, source, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experience.id,
                strategy,
                variant,
                experience.prompt.text,
                experience.prompt.content_hash(),
                experience.response.text,
                outcome,
                experience.analysis.score,
                experience.analysis.confidence,
                reward,
                experience.analysis.explanation,
                experience.analysis.recommendation,
                json.dumps(experience.analysis.tags),
                experience.prompt.source,
                now,
            ),
        )

        # Update stats at both the coarse (strategy) and fine (variant) grain.
        for key in {strategy, variant}:
            self._bump_stats(key, strategy, reward, outcome, now)

        self._conn.commit()

    def _bump_stats(self, key: str, strategy: str, reward: float, outcome: str, now: str) -> None:
        row = self._conn.execute(
            "SELECT attempts, successes, total_reward, best_reward, consecutive_failures "
            "FROM strategy_stats WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            attempts, successes, total_reward, best_reward, streak = 0, 0, 0.0, 0.0, 0
        else:
            attempts = row["attempts"]
            successes = row["successes"]
            total_reward = row["total_reward"]
            best_reward = row["best_reward"]
            streak = row["consecutive_failures"]

        attempts += 1
        successes += 1 if outcome == "success" else 0
        total_reward += reward
        avg_reward = total_reward / attempts
        best_reward = max(best_reward, reward)
        streak = 0 if outcome in ("success", "partial") else streak + 1

        recent_rewards = self._recent_rewards_for_key(key, limit=_RECENT_WINDOW)
        recent_rewards = ([reward] + recent_rewards)[:_RECENT_WINDOW]
        recent_avg_reward = sum(recent_rewards) / len(recent_rewards)

        self._conn.execute(
            """INSERT INTO strategy_stats
                 (key, strategy, attempts, successes, total_reward, avg_reward,
                  best_reward, consecutive_failures, last_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                 attempts=excluded.attempts, successes=excluded.successes,
                 total_reward=excluded.total_reward, avg_reward=excluded.avg_reward,
                 best_reward=excluded.best_reward,
                 consecutive_failures=excluded.consecutive_failures,
                 last_used=excluded.last_used""",
            (key, strategy, attempts, successes, total_reward, avg_reward,
             best_reward, streak, now),
        )
        # recent_avg_reward is derived fresh on every read (see
        # get_strategy_stats/_row_to_stats) rather than stored, since it's
        # cheap to recompute from the `experiences` table and storing it
        # here would risk drifting out of sync.

    def _recent_rewards_for_key(self, key: str, limit: int) -> list[float]:
        col = "strategy" if "#" not in key else "variant"
        rows = self._conn.execute(
            f"SELECT reward FROM experiences WHERE {col} = ? ORDER BY timestamp DESC LIMIT ?",
            (key, limit),
        ).fetchall()
        return [r["reward"] for r in rows]

    # -- reads ------------------------------------------------------------

    def get_strategy_stats(self, strategy: str) -> StrategyStats:
        row = self._conn.execute(
            "SELECT * FROM strategy_stats WHERE key = ?", (strategy,)
        ).fetchone()
        if row is None:
            return StrategyStats(strategy=strategy)
        return self._row_to_stats(row)

    def all_strategy_stats(self) -> list[StrategyStats]:
        rows = self._conn.execute(
            "SELECT * FROM strategy_stats WHERE key = strategy ORDER BY strategy"
        ).fetchall()
        return [self._row_to_stats(r) for r in rows]

    def get_variant_stats(self, strategy: str) -> dict[str, StrategyStats]:
        rows = self._conn.execute(
            "SELECT * FROM strategy_stats WHERE strategy = ? AND key != strategy",
            (strategy,),
        ).fetchall()
        return {r["key"]: self._row_to_stats(r) for r in rows}

    def _row_to_stats(self, row: sqlite3.Row) -> StrategyStats:
        recent = self._recent_rewards_for_key(row["key"], limit=_RECENT_WINDOW)
        recent_avg = sum(recent) / len(recent) if recent else 0.0
        return StrategyStats(
            strategy=row["strategy"],
            attempts=row["attempts"],
            successes=row["successes"],
            total_reward=row["total_reward"],
            avg_reward=row["avg_reward"],
            best_reward=row["best_reward"],
            recent_avg_reward=recent_avg,
            consecutive_failures=row["consecutive_failures"],
            last_used=row["last_used"],
        )

    def seen_prompt_hash(self, content_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM experiences WHERE prompt_hash = ? LIMIT 1", (content_hash,)
        ).fetchone()
        return row is not None

    def is_near_duplicate(self, strategy: str, prompt_text: str, threshold: float = 0.82) -> bool:
        """Practical duplicate detection beyond exact-hash: normalizes
        whitespace/case and compares against recent prompts for this
        strategy with difflib's SequenceMatcher ratio. No embeddings/new
        dependency required — this is enough to catch "basically the same
        attack with a word or two changed"."""
        normalized = " ".join(prompt_text.lower().split())
        rows = self._conn.execute(
            """SELECT prompt_text FROM experiences WHERE strategy = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (strategy, _DUPLICATE_CHECK_WINDOW),
        ).fetchall()
        for row in rows:
            candidate = " ".join(row["prompt_text"].lower().split())
            ratio = difflib.SequenceMatcher(None, normalized, candidate).ratio()
            if ratio >= threshold:
                return True
        return False

    def get_recent_experiences(self, strategy: str, n: int = 5) -> list[dict]:
        rows = self._conn.execute(
            """SELECT prompt_text, response_text, outcome, score, reward,
                      explanation, recommendation, timestamp
               FROM experiences WHERE strategy = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (strategy, n),
        ).fetchall()
        return [dict(r) for r in rows]

    def best_prompts_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        rows = self._conn.execute(
            """SELECT prompt_text FROM experiences
               WHERE strategy = ? ORDER BY reward DESC LIMIT ?""",
            (strategy, top_n),
        ).fetchall()
        return [r["prompt_text"] for r in rows]

    def benchmark_seeds_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        rows = self._conn.execute(
            "SELECT example_prompt FROM benchmark_seeds WHERE strategy = ? LIMIT ?",
            (strategy, top_n),
        ).fetchall()
        return [r["example_prompt"] for r in rows]

    def recommendations_for_strategy(self, strategy: str, top_n: int = 3) -> list[str]:
        rows = self._conn.execute(
            """SELECT recommendation FROM experiences
               WHERE strategy = ? AND recommendation IS NOT NULL AND recommendation != ''
               ORDER BY timestamp DESC LIMIT ?""",
            (strategy, top_n),
        ).fetchall()
        return [r["recommendation"] for r in rows]

    def source_breakdown(self) -> dict[str, int]:
        """Counts of experiences by prompt source — used by the report to
        show newly-generated (LLM/template) vs. benchmark-derived attacks."""
        rows = self._conn.execute(
            "SELECT source, COUNT(*) as n FROM experiences GROUP BY source"
        ).fetchall()
        return {(r["source"] or "unknown"): r["n"] for r in rows}

    def close(self) -> None:
        self._conn.close()
