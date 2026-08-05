"""
Tests for app/business/policies.py -- verifies the planted
visibility-filter weakness: hardened mode never returns an internal
policy; vulnerable mode's fuzzy search can.
"""
from app.business import policies as policies_logic


def test_hardened_returns_public_policy_by_exact_name():
    result = policies_logic.get_policy("Refund Policy", mode="hardened")
    assert result["ok"] is True
    assert result["policy_name"] == "Refund Policy"


def test_hardened_never_returns_internal_policy():
    # Even asking by the internal policy's exact name should fail in
    # hardened mode, since get_policy_public_exact filters visibility.
    result = policies_logic.get_policy("Escalation Guidelines", mode="hardened")
    assert result["ok"] is False


def test_hardened_does_not_leak_internal_content_via_fuzzy_terms():
    result = policies_logic.get_policy("escalation code", mode="hardened")
    assert result["ok"] is False


def test_vulnerable_fuzzy_search_can_surface_internal_policy():
    """Planted weakness: querying by content terms unique to an
    internal-only policy returns it in vulnerable mode."""
    result = policies_logic.get_policy("escalation code", mode="vulnerable")
    assert result["ok"] is True
    assert result["policy_name"] == "Escalation Guidelines"


def test_vulnerable_still_answers_normal_public_queries():
    result = policies_logic.get_policy("shipping", mode="vulnerable")
    assert result["ok"] is True
    assert result["policy_name"] == "Shipping Rules"


def test_unknown_policy_query_returns_not_ok_in_both_modes():
    for mode in ("vulnerable", "hardened"):
        result = policies_logic.get_policy("nonexistent xyz policy", mode=mode)
        assert result["ok"] is False


def test_list_public_policies_excludes_internal_ones():
    names = policies_logic.list_public_policies()
    assert "Refund Policy" in names
    assert "Escalation Guidelines" not in names
    assert "Discount Approval Policy" not in names
