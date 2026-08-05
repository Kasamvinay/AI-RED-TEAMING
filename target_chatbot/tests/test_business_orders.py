"""
Tests for app/business/orders.py -- verifies the planted authorization
weakness behaves as designed: vulnerable mode is bypassable with any
non-empty email, hardened mode requires the correct one.
"""
from app.business import orders as orders_logic

# Alice Johnson (customer_id 1) owns ORD-1001; her real email is
# alice.johnson@example.com per seed data.
REAL_OWNER_EMAIL = "alice.johnson@example.com"
WRONG_EMAIL = "attacker@example.com"


def test_hardened_requires_correct_email():
    result = orders_logic.get_order_status("ORD-1001", REAL_OWNER_EMAIL, mode="hardened")
    assert result["ok"] is True
    assert result["order"]["order_id"] == "ORD-1001"


def test_hardened_rejects_wrong_email():
    result = orders_logic.get_order_status("ORD-1001", WRONG_EMAIL, mode="hardened")
    assert result["ok"] is False
    assert result["reason"] == "unauthorized"


def test_hardened_rejects_missing_email():
    result = orders_logic.get_order_status("ORD-1001", None, mode="hardened")
    assert result["ok"] is False


def test_vulnerable_accepts_any_nonempty_email_bola():
    """This is the planted weakness: presence, not correctness, of an
    email is enough in vulnerable mode."""
    result = orders_logic.get_order_status("ORD-1001", WRONG_EMAIL, mode="vulnerable")
    assert result["ok"] is True
    assert result["order"]["order_id"] == "ORD-1001"


def test_vulnerable_still_requires_some_email():
    result = orders_logic.get_order_status("ORD-1001", None, mode="vulnerable")
    assert result["ok"] is False


def test_order_not_found_in_either_mode():
    for mode in ("vulnerable", "hardened"):
        result = orders_logic.get_order_status("ORD-9999", REAL_OWNER_EMAIL, mode=mode)
        assert result["ok"] is False
        assert result["reason"] == "not_found"


def test_returned_order_never_includes_raw_customer_id():
    result = orders_logic.get_order_status("ORD-1001", REAL_OWNER_EMAIL, mode="hardened")
    assert "customer_id" not in result["order"]
