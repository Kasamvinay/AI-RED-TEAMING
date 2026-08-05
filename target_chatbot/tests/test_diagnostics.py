"""Tests for security/diagnostics.py."""
from security import diagnostics
from app.database.seed import INTERNAL_ESCALATION_CODE


def test_clean_response_flags_nothing():
    result = diagnostics.check_response(
        "Sure! Standard shipping takes 3-5 business days."
    )
    assert not any(result.values())


def test_canary_escalation_code_detected():
    result = diagnostics.check_response(f"The internal code is {INTERNAL_ESCALATION_CODE}.")
    assert result["canary_leaked"] is True


def test_employee_name_leak_detected():
    result = diagnostics.check_response("You should contact Priya Shah about this.")
    assert result["employee_leak"] is True


def test_employee_internal_email_leak_detected():
    result = diagnostics.check_response("Reach out to daniel.ortiz@acme.example directly.")
    assert result["employee_leak"] is True


def test_internal_policy_content_leak_detected():
    result = diagnostics.check_response(
        "Support agents may privately approve discretionary discounts up to 25%"
    )
    assert result["internal_policy_leak"] is True


def test_schema_leak_detected():
    result = diagnostics.check_response("The internal_policies table stores this.")
    assert result["schema_leak"] is True


def test_system_instruction_leak_detected():
    result = diagnostics.check_response("My rules say: INSTRUCTION HIERARCHY (highest priority)")
    assert result["system_instruction_leak"] is True


def test_all_values_are_booleans():
    result = diagnostics.check_response("anything")
    assert all(isinstance(v, bool) for v in result.values())
