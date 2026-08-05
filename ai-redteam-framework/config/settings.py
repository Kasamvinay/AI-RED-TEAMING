"""
config/settings.py

Loads config/config.yaml into a plain dict, with environment variables
available for secrets (API keys are NEVER stored in config.yaml) and for
target-connection settings (so switching targets, e.g. onto a local REST
chatbot, never requires editing the yaml file — just .env).

LLM CALL: none.
"""

from __future__ import annotations

import os

import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — falls back to real env vars only


def load_config(path: str = _CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    _apply_target_env_overrides(config)
    return config


def _apply_target_env_overrides(config: dict) -> None:
    """Overlays TARGET_TYPE / TARGET_BASE_URL / TARGET_TIMEOUT_SECONDS /
    TARGET_RESET_BETWEEN_ATTACKS onto config["target"] if set in the
    environment (typically via .env). Config.yaml values remain the
    defaults when the corresponding env var isn't set.

    TARGET_TYPE=REST maps to the AcmeSupportBotAdapter specifically
    (session_id + /reset support) rather than the generic RestApiAdapter,
    since that's the adapter TARGET_BASE_URL/TARGET_RESET_BETWEEN_ATTACKS
    are meaningful for. Use target.adapter: rest_api directly in
    config.yaml (not this env var) if you want the generic, non-session
    REST adapter instead.
    """
    target = config.setdefault("target", {})

    target_type = os.environ.get("TARGET_TYPE")
    if target_type:
        target["adapter"] = "acme_supportbot" if target_type.strip().upper() == "REST" else target_type.strip().lower()

    base_url = os.environ.get("TARGET_BASE_URL")
    if base_url:
        target["base_url"] = base_url

    timeout_seconds = os.environ.get("TARGET_TIMEOUT_SECONDS")
    if timeout_seconds:
        target["timeout_seconds"] = float(timeout_seconds)

    reset_between_attacks = os.environ.get("TARGET_RESET_BETWEEN_ATTACKS")
    if reset_between_attacks:
        target["reset_between_attacks"] = reset_between_attacks.strip().lower() in ("1", "true", "yes", "on")


def get_openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")
