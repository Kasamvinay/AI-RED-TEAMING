"""
llm/factory.py

The single place in the whole framework that knows how many providers
exist and how to pick between them. Everything else — Attack Generator,
Attack Analyst, main.py's wiring — just calls `LLMFactory.create()` and
gets back a `BaseLLMClient`, without caring whether that's OpenAI,
Gemini, or Groq underneath.

Provider selection is entirely configuration-driven via the LLM_PROVIDER
environment variable (falls back to config.yaml's `llm.provider` if the
env var isn't set, and defaults to "openai" if neither is set). Per-role
temperature/max_tokens still come from config.yaml as before (generator.*
/ judge.* sections) — only the underlying provider/model/API key
resolution changed.

To add a new provider later (Anthropic, OpenRouter, Azure OpenAI,
Together AI, ...): write one new llm/<provider>_client.py implementing
BaseLLMClient, register it in `_CLIENT_CLASSES` below, and add its
`<PROVIDER>_API_KEY` / `<PROVIDER>_MODEL` env vars. Nothing else in the
framework needs to change.
"""

from __future__ import annotations

import os
from typing import Optional

from llm.base_client import BaseLLMClient
from llm.gemini_client import DEFAULT_MODEL as _GEMINI_DEFAULT_MODEL
from llm.gemini_client import GeminiClient
from llm.groq_client import DEFAULT_MODEL as _GROQ_DEFAULT_MODEL
from llm.groq_client import GroqClient
from llm.openai_client import DEFAULT_MODEL as _OPENAI_DEFAULT_MODEL
from llm.openai_client import OpenAIClient

# Registry: provider name -> (client class, API-key env var, model env var, default model)
_PROVIDERS: dict[str, tuple[type[BaseLLMClient], str, str, str]] = {
    "openai": (OpenAIClient, "OPENAI_API_KEY", "OPENAI_MODEL", _OPENAI_DEFAULT_MODEL),
    "gemini": (GeminiClient, "GEMINI_API_KEY", "GEMINI_MODEL", _GEMINI_DEFAULT_MODEL),
    "groq": (GroqClient, "GROQ_API_KEY", "GROQ_MODEL", _GROQ_DEFAULT_MODEL),
}


class LLMFactory:
    @staticmethod
    def available_providers() -> list[str]:
        return list(_PROVIDERS.keys())

    @staticmethod
    def create(
        provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        """
        Builds a BaseLLMClient for the selected provider.

        Resolution order for the provider itself: explicit `provider` arg
        -> LLM_PROVIDER env var -> "openai" default.
        Resolution order for model/api_key: explicit arg -> the
        provider's own <PROVIDER>_MODEL / <PROVIDER>_API_KEY env var ->
        that provider's built-in default model (api_key has no fallback —
        it's a hard requirement).

        Raises ValueError (a setup/configuration error, not an LLMError —
        LLMError is reserved for runtime provider failures after a client
        already exists) if the provider name is unknown or its API key is
        missing.
        """
        resolved_provider = (provider or os.environ.get("LLM_PROVIDER") or "openai").strip().lower()

        if resolved_provider not in _PROVIDERS:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{resolved_provider}'. "
                f"Available providers: {', '.join(LLMFactory.available_providers())}"
            )

        client_cls, key_env_var, model_env_var, default_model = _PROVIDERS[resolved_provider]

        resolved_api_key = api_key or os.environ.get(key_env_var)
        if not resolved_api_key:
            raise ValueError(
                f"No API key found for provider '{resolved_provider}'. "
                f"Set {key_env_var} in your environment or .env file."
            )

        resolved_model = model or os.environ.get(model_env_var) or default_model

        return client_cls(
            api_key=resolved_api_key,
            model=resolved_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
