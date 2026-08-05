"""
core/call_tracker.py

A trivial shared counter for real OpenAI API calls, used to enforce the
one truly global safety limit requested for this experimental phase:
`RunConfig.max_total_api_calls`, checked across ALL three roles
(Prompt Generator, Target Model, Attack Analyst) combined, regardless of
how generous each role's own individual budget is.

This exists because the per-component caps (generator retries, analyst
max_llm_calls) are each reasonable in isolation but say nothing about
total spend across a run — this is the backstop that prevents an
accidental infinite loop or runaway cost regardless of what the
individual components are configured to allow.

Deliberately not fancier than this: one shared, mutable counter object,
passed by reference into whichever components make real API calls, and
checked by the Orchestrator once per iteration.

LLM CALL: none — this file only counts them.
"""

from __future__ import annotations


class ApiCallTracker:
    def __init__(self):
        self.total = 0
        self.by_role: dict[str, int] = {"generator": 0, "target": 0, "analyst": 0}

    def record(self, role: str = "unspecified", n: int = 1) -> None:
        self.total += n
        self.by_role[role] = self.by_role.get(role, 0) + n

    def remaining(self, budget: int) -> int:
        return max(0, budget - self.total)

    def exceeded(self, budget: int) -> bool:
        return self.total >= budget
