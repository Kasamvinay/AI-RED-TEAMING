"""
adapters/acme_supportbot_adapter.py

Target System Adapter for the locally-running Acme SupportBot FastAPI
target (Qwen2.5 via Ollama). This is a NEW, additive file — it doesn't
modify RestApiAdapter/EnterpriseChatbotAdapter in rest_api_adapter.py,
which stay exactly as they were for other generic REST targets.

Why a dedicated class instead of reusing RestApiAdapter directly: the
Acme target is *session-based* (POST /chat takes a session_id and keeps
conversation history server-side; POST /reset/{session_id} clears it).
RestApiAdapter's request_builder only ever sees a single prompt string —
it has no concept of a session id or a reset call. Everything else about
this adapter (the try/except error-handling shape, the TargetResponse
contract) deliberately mirrors RestApiAdapter/OpenAIAdapter exactly, so
it's a drop-in TargetSystemAdapter like any other.

Session semantics (per attack, not per run):
- Every `send()` call gets its OWN fresh session_id, so unrelated attack
  attempts within the same orchestrator run never contaminate each
  other's conversation history on the target side.
- Every `send_conversation()` call also gets its own fresh session_id,
  reused across all turns of that one multi-turn session (so the target's
  real history mechanism is exercised for multi_turn_escalation), then
  discarded.
- If `reset_between_attacks` is enabled, the adapter also explicitly
  calls POST /reset/{session_id} before the first message of a session —
  redundant with the fresh-uuid guarantee, but cheap, explicit, and
  matches the spec's "generate a fresh session_id OR call reset" as a
  belt-and-suspenders default.

Timeouts and retries: local CPU inference through Ollama can legitimately
take 30–120+ seconds. `timeout_seconds` defaults high (300s) and is fully
configurable. There is NO retry logic — a single slow-but-successful
request must never be duplicated by a retry loop.

LLM CALL: none directly — performs an HTTP call to the locally-running
Acme SupportBot, which is itself backed by a local Qwen model via Ollama.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

import requests

from core.interfaces import TargetSystemAdapter
from core.types import AttackPrompt, TargetResponse

logger = logging.getLogger("redteam.adapter.acme_supportbot")


class AcmeSupportBotAdapter(TargetSystemAdapter):
    name = "acme_supportbot_adapter"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: float = 300.0,
        reset_between_attacks: bool = True,
        session_id_prefix: str = "redteam",
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/chat"
        self.timeout_seconds = timeout_seconds
        self.reset_between_attacks = reset_between_attacks
        self.session_id_prefix = session_id_prefix

    # -- session helpers ----------------------------------------------

    def _new_session_id(self) -> str:
        return f"{self.session_id_prefix}-{uuid.uuid4().hex[:12]}"

    def _reset_session(self, session_id: str) -> None:
        if not self.reset_between_attacks:
            return
        try:
            requests.post(f"{self.base_url}/reset/{session_id}", timeout=self.timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            # A failed reset on a brand-new (never-used) session id is not
            # fatal — log it and proceed; the fresh uuid already guarantees
            # there's nothing to reset in practice.
            logger.warning("Reset call failed for session %s (continuing anyway): %s", session_id, exc)

    def _post_chat(self, message: str, session_id: str) -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Single, non-retrying POST /chat call.
        Returns (response_text, raw_payload, error_message)."""
        try:
            resp = requests.post(
                self.chat_url,
                json={"message": message, "session_id": session_id},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            return None, None, (
                f"Target timed out after {self.timeout_seconds:.0f}s. This can be normal for "
                "slow CPU-bound local inference — consider raising TARGET_TIMEOUT_SECONDS / "
                "timeout_seconds if this happens often rather than treating it as a real error."
            )
        except requests.exceptions.ConnectionError as exc:
            return None, None, f"Could not connect to target at {self.chat_url} (is FastAPI running?): {exc}"
        except requests.exceptions.HTTPError as exc:
            return None, None, f"Target returned an HTTP error: {exc}"
        except requests.exceptions.RequestException as exc:  # noqa: BLE001
            return None, None, f"Request to target failed: {exc}"

        try:
            payload = resp.json()
        except ValueError as exc:
            return None, None, f"Target response was not valid JSON: {exc}"

        if "response" not in payload:
            return None, payload, f"Target JSON had no 'response' field. Got keys: {list(payload.keys())}"

        return str(payload["response"]), payload, None

    # -- TargetSystemAdapter contract ----------------------------------

    def send(self, prompt: AttackPrompt) -> TargetResponse:
        session_id = self._new_session_id()
        self._reset_session(session_id)

        start = time.perf_counter()
        text, payload, error = self._post_chat(prompt.text, session_id)
        duration_s = time.perf_counter() - start

        logger.info("Target response received in %.1fs (session=%s, error=%s)",
                    duration_s, session_id, bool(error))

        return TargetResponse(
            prompt_id=prompt.id,
            text=text or "",
            raw=payload,
            latency_ms=duration_s * 1000,
            adapter_name=self.name,
            error=error,
        )

    def send_conversation(self, turns: list[str]) -> TargetResponse:
        session_id = self._new_session_id()
        self._reset_session(session_id)

        start = time.perf_counter()
        transcript = []
        last_text = ""
        error = None

        for i, turn_text in enumerate(turns):
            turn_start = time.perf_counter()
            text, payload, turn_error = self._post_chat(turn_text, session_id)
            turn_duration_s = time.perf_counter() - turn_start

            logger.info("Turn %d/%d response received in %.1fs (session=%s, error=%s)",
                        i + 1, len(turns), turn_duration_s, session_id, bool(turn_error))

            if turn_error:
                error = turn_error
                break  # stop the session on first failure — don't keep sending turns blind

            transcript.append({"turn": i + 1, "user": turn_text, "assistant": text})
            last_text = text or ""

        return TargetResponse(
            prompt_id="multi-turn",
            text=last_text,
            raw={"transcript": transcript, "session_id": session_id},
            latency_ms=(time.perf_counter() - start) * 1000,
            adapter_name=self.name,
            error=error,
        )
