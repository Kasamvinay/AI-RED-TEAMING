"""
adapters/rest_api_adapter.py

Target System Adapter for any HTTP JSON chatbot endpoint — the shape most
"enterprise chatbot" and internal copilot integrations take in practice.

Configure it with:
- url: the chat endpoint
- request_builder: fn(prompt_text) -> JSON-serializable request body
- response_parser: fn(json_response) -> reply text

This lets one adapter class cover many different enterprise APIs without
subclassing, as long as they're "POST JSON, get JSON back".

LLM CALL: none directly in this file — it just performs an HTTP call to
whatever system you point it at (that system may itself call an LLM).
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import requests

from core.interfaces import TargetSystemAdapter
from core.types import AttackPrompt, TargetResponse

RequestBuilder = Callable[[str], dict]
ResponseParser = Callable[[dict], str]


def _default_request_builder(prompt_text: str) -> dict:
    return {"message": prompt_text}


def _default_response_parser(payload: dict) -> str:
    # Reasonable default for common shapes: {"reply": "..."} or {"response": "..."}
    for key in ("reply", "response", "message", "text", "output"):
        if key in payload:
            return str(payload[key])
    return str(payload)


class RestApiAdapter(TargetSystemAdapter):
    name = "rest_api_adapter"

    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        request_builder: RequestBuilder = _default_request_builder,
        response_parser: ResponseParser = _default_response_parser,
        timeout_seconds: float = 30.0,
    ):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.request_builder = request_builder
        self.response_parser = response_parser
        self.timeout_seconds = timeout_seconds

    def send(self, prompt: AttackPrompt) -> TargetResponse:
        start = time.perf_counter()
        body = self.request_builder(prompt.text)
        try:
            resp = requests.post(
                self.url, json=body, headers=self.headers, timeout=self.timeout_seconds
            )
            resp.raise_for_status()
            payload = resp.json()
            text = self.response_parser(payload)
            return TargetResponse(
                prompt_id=prompt.id,
                text=text,
                raw=payload,
                latency_ms=(time.perf_counter() - start) * 1000,
                adapter_name=self.name,
            )
        except Exception as exc:  # noqa: BLE001
            return TargetResponse(
                prompt_id=prompt.id,
                text="",
                latency_ms=(time.perf_counter() - start) * 1000,
                adapter_name=self.name,
                error=str(exc),
            )


class EnterpriseChatbotAdapter(RestApiAdapter):
    """
    Thin, semantically-named subclass for the primary enterprise use case
    (customer support chatbot). Same behavior as RestApiAdapter — the
    separate class exists so config files and logs read clearly, and so
    enterprise-specific defaults (auth headers, retry policy, etc.) have
    an obvious place to live as the project grows.
    """

    name = "enterprise_chatbot_adapter"
