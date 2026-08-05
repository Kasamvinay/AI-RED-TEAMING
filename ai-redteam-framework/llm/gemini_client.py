"""
llm/gemini_client.py

Google Gemini implementation of BaseLLMClient. Deliberately uses plain
`requests` against the Gemini REST API rather than adding the
`google-generativeai` SDK as a dependency — keeps the framework's
dependency footprint the same as before this refactor (requests, PyYAML,
python-dotenv, openai were already required; nothing new to install for
Gemini specifically).

Gemini's API shape differs from OpenAI's in two ways this client bridges:
- No "system" role in `contents` — system text goes in a separate
  `system_instruction` field.
- Assistant turns are role "model", not "assistant".

Both translations happen transparently inside `generate()`; callers still
pass the same OpenAI-style `messages` list as every other provider.
"""

from __future__ import annotations

from typing import Optional

import requests

from llm.base_client import (
    BaseLLMClient,
    InvalidAPIKeyError,
    LLMTimeoutError,
    MalformedResponseError,
    ProviderUnavailableError,
    RateLimitError,
)

DEFAULT_MODEL = "gemini-2.0-flash"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _to_gemini_payload(messages: list[dict], temperature: float, max_tokens: int) -> dict:
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    contents = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue  # folded into system_instruction below
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": m.get("content", "")}]})

    payload: dict = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_parts:
        payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    return payload


class GeminiClient(BaseLLMClient):
    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 500,
        timeout_seconds: float = 60.0,
    ):
        self.api_key = api_key
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        url = f"{_API_BASE}/{self.model}:generateContent?key={self.api_key}"
        payload = _to_gemini_payload(
            messages,
            temperature if temperature is not None else self.default_temperature,
            max_tokens if max_tokens is not None else self.default_max_tokens,
        )

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            raise LLMTimeoutError(f"Gemini request timed out: {exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ProviderUnavailableError(f"Could not reach Gemini: {exc}") from exc
        except requests.exceptions.RequestException as exc:  # noqa: BLE001
            raise ProviderUnavailableError(f"Gemini request failed: {exc}") from exc

        try:
            body = resp.json()
        except ValueError as exc:
            raise MalformedResponseError(f"Gemini response was not valid JSON: {exc}") from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise InvalidAPIKeyError(f"Gemini rejected the API key: {body}")
        if resp.status_code == 429:
            raise RateLimitError(f"Gemini rate-limited this request: {body}")
        if resp.status_code >= 400:
            error = body.get("error", {})
            status = str(error.get("status", ""))
            message = str(error.get("message", ""))
            if "API_KEY" in status.upper() or "api key" in message.lower():
                raise InvalidAPIKeyError(f"Gemini rejected the API key: {message}")
            if resp.status_code >= 500:
                raise ProviderUnavailableError(f"Gemini server error: {message or body}")
            raise ProviderUnavailableError(f"Gemini API error ({resp.status_code}): {message or body}")

        candidates = body.get("candidates")
        if not candidates:
            raise MalformedResponseError(f"Gemini response had no candidates: {body}")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise MalformedResponseError(f"Gemini response had no text part: {body}")
        return parts[0]["text"]
