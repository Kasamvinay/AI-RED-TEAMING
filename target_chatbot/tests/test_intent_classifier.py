"""Tests for app/services/intent_classifier.py."""
from app.services.intent_classifier import classify


def test_order_id_detected_and_wins_priority():
    result = classify("Hi, can you check ORD-1001 for me? my email is a@example.com")
    assert result.intent == "order_status"
    assert result.order_id == "ORD-1001"
    assert result.email == "a@example.com"


def test_order_status_keyword_without_id():
    result = classify("Where is my order? It's late.")
    assert result.intent == "order_status"
    assert result.order_id is None


def test_ticket_id_detected():
    result = classify("What's the status of TCK-2001?")
    assert result.intent == "ticket_status"
    assert result.ticket_id == "TCK-2001"


def test_ticket_status_keyword():
    result = classify("Can you check my tickets please")
    assert result.intent == "ticket_status"


def test_ticket_create_keyword():
    result = classify("My keyboard case arrived damaged, I want to report a problem")
    assert result.intent == "ticket_create"


def test_policy_question_keyword():
    result = classify("What is your refund policy?")
    assert result.intent == "policy_question"


def test_general_fallback():
    result = classify("Hello, how are you today?")
    assert result.intent == "general"


def test_email_extraction():
    result = classify("my email is test.user+tag@sub.example.co.uk")
    assert result.email == "test.user+tag@sub.example.co.uk"
