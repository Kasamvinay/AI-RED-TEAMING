"""
objectives/profiles.py

Loads ObjectiveProfile instances from the YAML files in this directory.
Each YAML file is a reusable "what does safe behavior mean for this kind
of system" profile, as required by the spec:

    Customer Support / Banking Assistant / HR Assistant / Generic Testing

Add a new objective by dropping a new YAML file here with the same shape
and it becomes available via `load_objective(name)` — no code changes
needed elsewhere in the framework.

LLM CALL: none. Pure file I/O and parsing.
"""

from __future__ import annotations

import os

import yaml

from core.types import ObjectiveProfile

_PROFILES_DIR = os.path.dirname(__file__)

_KNOWN_PROFILES = {
    "customer_support": "customer_support.yaml",
    "banking_assistant": "banking_assistant.yaml",
    "hr_assistant": "hr_assistant.yaml",
    "generic": "generic.yaml",
}


def load_objective(name: str) -> ObjectiveProfile:
    filename = _KNOWN_PROFILES.get(name)
    if not filename:
        raise ValueError(
            f"Unknown objective '{name}'. Known objectives: {list(_KNOWN_PROFILES)}"
        )
    path = os.path.join(_PROFILES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ObjectiveProfile(
        name=data["name"],
        system_prompt=data["system_prompt"].strip(),
        attack_goals=data.get("attack_goals", []),
        safety_expectations=data.get("safety_expectations", []),
        disallowed_topics=data.get("disallowed_topics", []),
        evaluation_notes=data.get("evaluation_notes", "").strip(),
    )


def list_available_objectives() -> list[str]:
    return list(_KNOWN_PROFILES.keys())
