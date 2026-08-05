"""
llm/openai_client.py

OpenAI implementation of BaseLLMClient. This is the ONLY file that
imports the `openai` package for the framework's own reasoning roles
(Attack Generator / Attack Analyst). The target-side OpenAIAdapter in
adapters/openai_adapter.py is unrelated — that's for when the SYSTEM
UNDER TEST happens to be OpenAI-backed, a completely different role, and
is intentionally left untouched by this refactor.
"""

from __future__ import annotations

from typing import Optional

from llm.base_client import (
    BaseLLMClient,
    InvalidAPIKeyError,
    LLMTimeoutError,
    MalformedResponseError,
    ProviderUnavailableError,
    RateLimitError,
)

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIClient(BaseLLMClient):
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ):
        try:
            import openai
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install with: pip install openai"
            ) from e
        self._openai = openai
        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens

    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
            )
        except self._openai.AuthenticationError as exc:
            raise InvalidAPIKeyError(f"OpenAI rejected the API key: {exc}") from exc
        except self._openai.RateLimitError as exc:
            raise RateLimitError(f"OpenAI rate-limited this request: {exc}") from exc
        except self._openai.APITimeoutError as exc:
            raise LLMTimeoutError(f"OpenAI request timed out: {exc}") from exc
        except self._openai.APIConnectionError as exc:
            raise ProviderUnavailableError(f"Could not reach OpenAI: {exc}") from exc
        except self._openai.APIError as exc:
            raise ProviderUnavailableError(f"OpenAI API error: {exc}") from exc

        try:
            text = completion.choices[0].message.content
        except (IndexError, AttributeError) as exc:
            raise MalformedResponseError(f"Unexpected OpenAI response shape: {exc}") from exc

        if text is None:
            raise MalformedResponseError("OpenAI returned an empty message content.")
        return text
