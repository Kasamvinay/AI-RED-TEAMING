"""
app/services/qwen_client.py

The ONLY file that knows a model server exists. Everything above this
(app/chatbot/agent.py) talks to `generate(messages) -> str` and nothing
else. Swap Qwen 3B -> 1.5B -> a different local model -> a hosted API by
editing only this file and app/config/settings.py (MODEL_NAME).

Calls a local Ollama server (http://localhost:11434 by default) running
a quantized Qwen2.5 GGUF model, so the model is loaded into memory once
by Ollama and reused across every request rather than reloaded per call.
"""
from typing import List, Dict

import httpx

from app.config import settings


class QwenClientError(RuntimeError):
    """Raised when the local model server can't be reached or errors out."""


class QwenClient:
    """
    Interface contract the rest of the app depends on:

        generate(messages: List[{"role": str, "content": str}]) -> str
    """

    def __init__(self, base_url: str = None, model_name: str = None,
                 temperature: float = None, max_output_tokens: int = None,
                 timeout_seconds: int = None):
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        self.model_name = model_name or settings.MODEL_NAME
        self.temperature = settings.TEMPERATURE if temperature is None else temperature
        self.max_output_tokens = (
            settings.MAX_OUTPUT_TOKENS if max_output_tokens is None else max_output_tokens
        )
        self.timeout_seconds = timeout_seconds or settings.REQUEST_TIMEOUT_SECONDS

    def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
            },
        }
        url = f"{self.base_url}/api/chat"
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout_seconds)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise QwenClientError(
                f"Could not reach Ollama at {self.base_url}. "
                f"Is `ollama serve` running and is '{self.model_name}' pulled? ({exc})"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise QwenClientError(
                f"Ollama returned an error status: {exc.response.status_code} {exc.response.text}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise QwenClientError(
                f"Request to Ollama timed out after {self.timeout_seconds}s. "
                f"CPU inference can be slow -- consider REQUEST_TIMEOUT_SECONDS, "
                f"a smaller model, or a shorter MAX_OUTPUT_TOKENS."
            ) from exc

        data = resp.json()
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise QwenClientError(f"Unexpected Ollama response shape: {data}") from exc


class FakeQwenClient:
    """Deterministic stand-in for QwenClient, used only in tests."""

    def __init__(self, canned_response: str = "This is a fake response."):
        self.canned_response = canned_response
        self.last_messages = None

    def generate(self, messages: List[Dict[str, str]]) -> str:
        self.last_messages = messages
        return self.canned_response
