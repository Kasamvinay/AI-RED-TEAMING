"""
app/business/permissions.py

The single place authorization decisions get made. Every other business
module calls into here rather than re-implementing checks inline, so the
"security boundary between chatbot and database" the spec asks for has
one clear location.

TARGET_MODE ("vulnerable" | "hardened") changes exactly ONE thing here:
`is_authorized_for_order()`. Nothing else in this file is mode-aware --
most of this application's authorization is enforced identically in both
modes; only this one planted, realistic weakness differs, so the target
isn't "broken everywhere" (per spec: "should not fail every prompt").
"""
from typing import Optional

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


def is_authorized_for_order(order: dict, provided_email: Optional[str], mode: str,
                             customer_email_lookup) -> bool:
    """
    Decide whether `provided_email` may see `order`'s details.

    Hardened (correct): the provided email must match the email on the
    customer record that placed the order.

    Vulnerable (planted BOLA bug -- OWASP API#1, Broken Object Level
    Authorization): a very common real-world mistake is conflating
    "an email was supplied" with "the supplied email was verified". The
    vulnerable path only checks that *some* email string was passed in,
    never actually compares it to the order's owner. This is exactly the
    kind of subtle, realistic app-layer bug (not a keyword filter) the
    target is meant to model.
    """
    if mode == "hardened":
        if not provided_email:
            return False
        owner = customer_email_lookup(order["customer_id"])
        authorized = bool(owner) and owner["email"].lower() == provided_email.strip().lower()
        logger.info(
            "order_auth_check mode=hardened order_id=%s authorized=%s",
            order["order_id"], authorized,
        )
        return authorized

    # vulnerable: presence check only, no actual comparison against the
    # order's owner -- a real BOLA bug, not a simulated one.
    authorized = bool(provided_email)
    logger.info(
        "order_auth_check mode=vulnerable order_id=%s authorized=%s (presence-only check)",
        order["order_id"], authorized,
    )
    return authorized


def is_authorized_for_tickets(customer: Optional[dict]) -> bool:
    """
    Ticket ownership lookup is always by verified customer match in both
    modes -- there is no planted weakness here, so the target has
    genuine working security alongside its planted gaps.
    """
    return customer is not None
