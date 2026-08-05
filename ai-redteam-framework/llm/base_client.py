"""
llm/base_client.py

The abstraction that makes the framework provider-agnostic. Every
component that needs to "call an LLM to reason" (Attack Generator, Attack
Analyst) talks ONLY to this interface — never to openai/google/groq SDKs
directly. Which provider is actually behind it is decided once, in
llm/factory.py, from configuration.

    BaseLLMClient.generate(messages) -> str

`messages` is always the familiar OpenAI-style list of
`{"role": "system"|"user"|"assistant", "content": str}` dicts, regardless
of which provider is selected — each concrete client is responsible for
translating that into whatever shape its provider's API actually wants
(see llm/gemini_client.py for the most divergent example).

Exception hierarchy: every concrete client normalizes its provider's own
errors into these, so callers (attacks/prompt_generator.py,
judge/attack_analyst.py) can handle "the LLM layer failed" once, generically,
without knowing or caring which provider raised it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LLMError(Exception):
    """Base class for all normalized LLM-provider errors."""


class InvalidAPIKeyError(LLMError):
    """The configured API key is missing, malformed, or rejected by the provider."""


class RateLimitError(LLMError):
    """The provider rejected the request due to rate limiting / quota."""


class LLMTimeoutError(LLMError):
    """The request to the provider timed out."""


class ProviderUnavailableError(LLMError):
    """Could not reach the provider at all (network/connection failure, 5xx, etc.)."""


class MalformedResponseError(LLMError):
    """The provider responded, but not in a shape we could extract text from."""


class BaseLLMClient(ABC):
    """Common interface every provider client implements. Role-specific
    defaults (temperature, max_tokens) are bound at construction time
    (via llm/factory.py) so call sites can simply do
    `llm_client.generate(messages)` without repeating them on every call,
    while still allowing a one-off override via the optional kwargs."""

    provider_name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Sends `messages` to the provider and returns the reply text.

        Raises one of the exceptions above on failure — never returns
        None and never raises a provider-specific exception type."""
        raise NotImplementedError
