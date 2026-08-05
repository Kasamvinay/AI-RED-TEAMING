"""
adapters/openai_adapter.py

Target System Adapter for an OpenAI-backed chatbot (e.g. a chat-completion
model you're evaluating, or a support bot built on top of one).

This is the ONLY file in the framework that imports the `openai` package
for the TARGET role. If you ever swap the target system, you add a new
adapter file next to this one — nothing in core/, judge/, attacks/, or
reporting/ changes.

Role isolation: this adapter's `system_prompt` is the TARGET's own
instructions (e.g. an ObjectiveProfile's system_prompt, standing in for
the real enterprise chatbot's configuration). It is a completely separate
OpenAI conversation from the Prompt Generator's conversation and the
Attack Analyst's conversation — neither of those ever sees this system
prompt, and this adapter never sees theirs. Each `send()`/`send_conversation()`
call starts fresh; conversation state is held only within one
`send_conversation()` call and is never carried over to the next one.

LLM CALL: yes — every `send()` is one call, and `send_conversation()` is
one call per turn (this is the system UNDER TEST, so these calls are
unavoidable — testing requires talking to the target for every turn of
every session).
"""

from __future__ import annotations

import os
import time
from typing import Optional

from core.interfaces import TargetSystemAdapter
from core.types import AttackPrompt, TargetResponse


class OpenAIAdapter(TargetSystemAdapter):
    name = "openai_adapter"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 400,
        api_call_tracker=None,
    ):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "The 'openai' package is required for OpenAIAdapter. "
                "Install with: pip install openai"
            ) from e

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "No OpenAI API key found. Either set the OPENAI_API_KEY "
                "environment variable, or copy .env.example to .env and "
                "fill it in (main.py loads .env automatically if "
                "python-dotenv is installed: pip install python-dotenv)."
            )
        self._client = OpenAI(api_key=resolved_key)
        self.model = model
        self.system_prompt = system_prompt or "You are a helpful assistant."
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_call_tracker = api_call_tracker

    def send(self, prompt: AttackPrompt) -> TargetResponse:
        start = time.perf_counter()
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt.text},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            if self.api_call_tracker is not None:
                self.api_call_tracker.record(role="target")
            text = completion.choices[0].message.content or ""
            latency_ms = (time.perf_counter() - start) * 1000
            return TargetResponse(
                prompt_id=prompt.id,
                text=text,
                raw=completion.model_dump() if hasattr(completion, "model_dump") else None,
                latency_ms=latency_ms,
                adapter_name=self.name,
            )
        except Exception as exc:  # noqa: BLE001 — surface any provider error uniformly
            return TargetResponse(
                prompt_id=prompt.id,
                text="",
                latency_ms=(time.perf_counter() - start) * 1000,
                adapter_name=self.name,
                error=str(exc),
            )

    def send_conversation(self, turns: list[str]) -> TargetResponse:
        """
        Real multi-turn exchange: one API call per turn, with the target's
        own prior replies fed back in as assistant messages — so turn 3
        genuinely sees how the target responded to turns 1 and 2. History
        lives only in the local `messages` list for this call; nothing
        persists to the next `send_conversation()` invocation, so unrelated
        attack sessions never mix.
        """
        start = time.perf_counter()
        messages = [{"role": "system", "content": self.system_prompt}]
        transcript = []
        last_text = ""
        try:
            for i, turn_text in enumerate(turns):
                messages.append({"role": "user", "content": turn_text})
                completion = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                if self.api_call_tracker is not None:
                    self.api_call_tracker.record(role="target")
                reply = completion.choices[0].message.content or ""
                messages.append({"role": "assistant", "content": reply})
                transcript.append({"turn": i + 1, "user": turn_text, "assistant": reply})
                last_text = reply

            return TargetResponse(
                prompt_id="multi-turn",
                text=last_text,
                raw={"transcript": transcript},
                latency_ms=(time.perf_counter() - start) * 1000,
                adapter_name=self.name,
            )
        except Exception as exc:  # noqa: BLE001
            return TargetResponse(
                prompt_id="multi-turn",
                text=last_text,
                raw={"transcript": transcript},
                latency_ms=(time.perf_counter() - start) * 1000,
                adapter_name=self.name,
                error=str(exc),
            )
