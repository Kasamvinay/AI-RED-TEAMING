"""
llm/groq_client.py

Groq implementation of BaseLLMClient. Groq exposes an OpenAI-compatible
REST API, so this reuses the `openai` package pointed at Groq's base_url
instead of pulling in a separate SDK dependency — same request/response
shape as OpenAIClient, just a different endpoint, key, and default model.
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

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqClient(BaseLLMClient):
    provider_name = "groq"

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
                "The 'openai' package is required for GroqClient (Groq's API is "
                "OpenAI-compatible, so we reuse the same SDK). Install with: pip install openai"
            ) from e
        self._openai = openai
        self._client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
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
            raise InvalidAPIKeyError(f"Groq rejected the API key: {exc}") from exc
        except self._openai.RateLimitError as exc:
            raise RateLimitError(f"Groq rate-limited this request: {exc}") from exc
        except self._openai.APITimeoutError as exc:
            raise LLMTimeoutError(f"Groq request timed out: {exc}") from exc
        except self._openai.APIConnectionError as exc:
            raise ProviderUnavailableError(f"Could not reach Groq: {exc}") from exc
        except self._openai.APIError as exc:
            raise ProviderUnavailableError(f"Groq API error: {exc}") from exc

        try:
            text = completion.choices[0].message.content
        except (IndexError, AttributeError) as exc:
            raise MalformedResponseError(f"Unexpected Groq response shape: {exc}") from exc

        if text is None:
            raise MalformedResponseError("Groq returned an empty message content.")
        return text
