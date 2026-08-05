"""
app/business/customers.py

Customer identity verification. This is how a session "authenticates" --
by supplying an email that matches an existing customer record. No
passwords are modeled (out of scope for this fictional demo); the email
match stands in for a verification step.
"""
from typing import Optional

from app.database import queries


def verify_customer(email: str) -> Optional[dict]:
    """Return the customer record for `email`, or None if not found."""
    if not email:
        return None
    return queries.find_customer_by_email(email)


def safe_profile(customer: dict) -> dict:
    """
    Fields safe to describe back to the customer themselves. Excludes
    nothing here (a customer may see their own profile fully), but this
    function exists as the single place that decides that, so a future
    field addition to the `customers` table doesn't automatically become
    visible without a decision being made here.
    """
    return {
        "name": customer["name"],
        "membership_level": customer["membership_level"],
        "reward_points": customer["reward_points"],
    }
