"""
app/services/intent_classifier.py

Deterministic, rule-based intent classification and entity extraction.
Deliberately NOT an LLM call: the AI model composes the final reply, but
which business-logic function to invoke is decided by ordinary Python
before the model is ever asked anything, so the model can never directly
cause a database query by "deciding" to -- it only sees the results
after the fact. This mirrors the "AI model should NOT directly query the
database" requirement.

This is intentionally simple keyword/regex matching, not a security
filter -- it exists to route legitimate requests, not to detect attacks.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

ORDER_ID_RE = re.compile(r"\bORD-\d{3,6}\b", re.IGNORECASE)
TICKET_ID_RE = re.compile(r"\bTCK-\d{3,6}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

_POLICY_KEYWORDS = [
    "refund policy", "refund", "shipping", "delivery time", "return policy",
    "returns", "discount", "escalation", "policy",
]
_TICKET_CREATE_KEYWORDS = [
    "file a complaint", "create a ticket", "open a ticket", "report a problem",
    "report an issue", "i have an issue", "having an issue", "arrived damaged",
    "arrived broken", "not working",
]
_TICKET_STATUS_KEYWORDS = [
    "status of my ticket", "check my ticket", "my ticket", "existing ticket",
    "open tickets", "my tickets",
]
_ORDER_STATUS_KEYWORDS = [
    "where is my order", "order status", "track my order", "my order",
    "order hasn't arrived", "order hasnt arrived", "shipment",
]


@dataclass
class ClassifiedIntent:
    intent: str  # order_status | ticket_status | ticket_create | policy_question | general
    order_id: Optional[str] = None
    ticket_id: Optional[str] = None
    email: Optional[str] = None
    policy_query: Optional[str] = None
    raw_message: str = ""


def _find_email(message: str) -> Optional[str]:
    m = EMAIL_RE.search(message)
    return m.group(0) if m else None


def _find_order_id(message: str) -> Optional[str]:
    m = ORDER_ID_RE.search(message)
    return m.group(0).upper() if m else None


def _find_ticket_id(message: str) -> Optional[str]:
    m = TICKET_ID_RE.search(message)
    return m.group(0).upper() if m else None


def classify(message: str) -> ClassifiedIntent:
    lower = message.lower()
    email = _find_email(message)
    order_id = _find_order_id(message)
    ticket_id = _find_ticket_id(message)

    # Priority: explicit IDs are the strongest signal.
    if order_id:
        return ClassifiedIntent("order_status", order_id=order_id, email=email, raw_message=message)
    if ticket_id or any(k in lower for k in _TICKET_STATUS_KEYWORDS):
        return ClassifiedIntent("ticket_status", ticket_id=ticket_id, email=email, raw_message=message)
    if any(k in lower for k in _ORDER_STATUS_KEYWORDS):
        return ClassifiedIntent("order_status", order_id=order_id, email=email, raw_message=message)
    if any(k in lower for k in _TICKET_CREATE_KEYWORDS):
        return ClassifiedIntent("ticket_create", email=email, raw_message=message)
    if any(k in lower for k in _POLICY_KEYWORDS):
        return ClassifiedIntent("policy_question", policy_query=message, email=email, raw_message=message)

    return ClassifiedIntent("general", email=email, raw_message=message)
