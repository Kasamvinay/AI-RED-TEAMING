"""
app/chatbot/agent.py

The orchestrator: session state + intent classification + business
logic calls + prompt assembly + model call + diagnostics. This is the
only module that ties the other layers together; it never talks to
app/database directly (only through app/business/*), and it never
contains authorization logic itself (that's app/business/permissions.py).
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from app.config import settings
from app.chatbot import prompts
from app.services.intent_classifier import classify
from app.business import orders as orders_logic
from app.business import tickets as tickets_logic
from app.business import policies as policies_logic
from security import diagnostics
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class SessionStore:
    """In-memory session state: conversation history + an optional
    verified email once a lookup has succeeded for this session."""

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, session_id: str) -> dict:
        return self._sessions.setdefault(
            session_id, {"history": [], "authenticated_email": None}
        )

    def get_history(self, session_id: str) -> List[dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            return list(session["history"]) if session else []

    def get_authenticated_email(self, session_id: str) -> Optional[str]:
        with self._lock:
            session = self._sessions.get(session_id)
            return session["authenticated_email"] if session else None

    def set_authenticated_email(self, session_id: str, email: str) -> None:
        with self._lock:
            self._get_or_create(session_id)["authenticated_email"] = email

    def append_turn(self, session_id: str, user_msg: dict, assistant_msg: dict) -> None:
        with self._lock:
            hist = self._get_or_create(session_id)["history"]
            hist.append(user_msg)
            hist.append(assistant_msg)

    def reset(self, session_id: str) -> bool:
        with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)
            return existed


class SupportAgent:
    def __init__(self, model_client, mode: Optional[str] = None,
                 max_history_turns: Optional[int] = None):
        self.model_client = model_client
        self.mode = mode or settings.TARGET_MODE
        self.max_history_turns = (
            settings.MAX_HISTORY_TURNS if max_history_turns is None else max_history_turns
        )
        self.sessions = SessionStore()

    # -- business-logic dispatch -----------------------------------------
    def _run_business_logic(self, session_id: str, classified) -> dict:
        """
        Returns a dict always containing at least:
            {"intent": str, "database_accessed": bool, "tables_used": [...]}
        plus intent-specific fields consumed by prompts.build_business_context_block.
        """
        intent = classified.intent
        effective_email = classified.email or self.sessions.get_authenticated_email(session_id)

        if intent == "order_status":
            if not classified.order_id:
                return {"intent": intent, "database_accessed": False, "tables_used": [],
                        "ok": False, "reason": "missing_order_id"}
            result = orders_logic.get_order_status(classified.order_id, effective_email, self.mode)
            result["intent"] = intent
            result["database_accessed"] = True
            if result.get("ok") and classified.email:
                self.sessions.set_authenticated_email(session_id, classified.email)
            return result

        if intent == "ticket_status":
            if not effective_email:
                return {"intent": intent, "database_accessed": False, "tables_used": [],
                        "ok": False, "reason": "missing_email"}
            result = tickets_logic.get_my_tickets(effective_email)
            result["intent"] = intent
            result["database_accessed"] = True
            if result.get("ok") and classified.email:
                self.sessions.set_authenticated_email(session_id, classified.email)
            return result

        if intent == "ticket_create":
            if not effective_email:
                return {"intent": intent, "database_accessed": False, "tables_used": [],
                        "ok": False, "reason": "missing_email"}
            result = tickets_logic.create_ticket(effective_email, classified.raw_message)
            result["intent"] = intent
            result["database_accessed"] = True
            if classified.email:
                self.sessions.set_authenticated_email(session_id, classified.email)
            return result

        if intent == "policy_question":
            query_text = classified.policy_query or classified.raw_message
            result = policies_logic.get_policy(query_text, self.mode)
            result["intent"] = intent
            result["database_accessed"] = True
            return result

        return {"intent": "general", "database_accessed": False, "tables_used": [], "ok": True}

    # -- message assembly ---------------------------------------------------
    def _build_messages(self, session_id: str, user_message: str, business_result: dict) -> List[dict]:
        system_prompt = prompts.get_system_prompt(self.mode)
        history = self.sessions.get_history(session_id)

        max_messages = self.max_history_turns * 2
        if len(history) > max_messages:
            history = history[-max_messages:]

        context_block = prompts.build_business_context_block(business_result, self.mode)
        wrapped_user = prompts.wrap_as_untrusted(user_message, self.mode)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        if context_block:
            messages.append({"role": "system", "content": context_block})
        messages.append({"role": "user", "content": wrapped_user})
        return messages

    # -- public entry point ---------------------------------------------------
    def send(self, session_id: str, user_message: str, include_diagnostics: bool = False) -> dict:
        start = time.monotonic()

        classified = classify(user_message)
        business_result = self._run_business_logic(session_id, classified)

        messages = self._build_messages(session_id, user_message, business_result)
        raw_response = self.model_client.generate(messages)

        self.sessions.append_turn(
            session_id,
            user_msg={"role": "user", "content": user_message},
            assistant_msg={"role": "assistant", "content": raw_response},
        )

        elapsed = time.monotonic() - start
        logger.info(
            "chat_turn session_id=%s intent=%s db_accessed=%s tables=%s elapsed=%.2fs",
            session_id, business_result["intent"], business_result["database_accessed"],
            business_result.get("tables_used", []), elapsed,
        )

        result = {
            "response": raw_response,
            "intent": business_result["intent"],
            "database_accessed": business_result["database_accessed"],
            "tables_used": business_result.get("tables_used", []),
            "processing_time": elapsed,
        }
        if include_diagnostics:
            result["diagnostics"] = diagnostics.check_response(raw_response)
        return result

    def reset_session(self, session_id: str) -> bool:
        return self.sessions.reset(session_id)
