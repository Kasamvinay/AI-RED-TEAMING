"""Tests for app/business/tickets.py."""
from app.business import tickets as tickets_logic

KNOWN_EMAIL = "brian.kim@example.com"  # customer_id 2 in seed data
UNKNOWN_EMAIL = "brand.new.customer@example.com"


def test_create_ticket_links_known_customer():
    result = tickets_logic.create_ticket(KNOWN_EMAIL, "My sync keeps failing.")
    assert result["ok"] is True
    assert result["linked_to_customer"] is True
    assert result["ticket_id"].startswith("TCK-")


def test_create_ticket_allows_guest_for_unknown_email():
    result = tickets_logic.create_ticket(UNKNOWN_EMAIL, "First time customer, need help.")
    assert result["ok"] is True
    assert result["linked_to_customer"] is False


def test_get_my_tickets_requires_matching_email():
    result = tickets_logic.get_my_tickets(KNOWN_EMAIL)
    assert result["ok"] is True
    assert isinstance(result["tickets"], list)


def test_get_my_tickets_rejects_unknown_email():
    result = tickets_logic.get_my_tickets("totally.unregistered@example.com")
    assert result["ok"] is False
    assert result["reason"] == "unauthorized"


def test_ticket_view_never_includes_assigned_agent_or_customer_id():
    result = tickets_logic.get_my_tickets("alice.johnson@example.com")
    assert result["ok"] is True
    for t in result["tickets"]:
        assert "assigned_agent" not in t
        assert "customer_id" not in t
