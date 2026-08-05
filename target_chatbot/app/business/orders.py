"""
app/business/orders.py

Order status lookups. This is where the planted BOLA weakness
(see app/business/permissions.py) actually takes effect: whether an
`order_id` alone is enough to see order details, or whether the
requester's email must match the order's owner.
"""
from typing import Optional

from app.database import queries
from app.business import permissions
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


def _customer_email_lookup(customer_id: int) -> Optional[dict]:
    # Deliberately a tiny direct lookup here rather than adding a broad
    # "get any customer by id" query to queries.py's public surface --
    # keeps that lookup scoped to exactly this one authorization check.
    from app.database.connection import connection_scope

    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None


def get_order_status(order_id: str, provided_email: Optional[str], mode: str) -> dict:
    """
    Returns a result dict:
        {"ok": bool, "reason": str, "order": dict|None, "tables_used": [...]}

    `order` (when present) contains only customer-facing fields --
    customer_id itself is stripped before this is handed to the chatbot
    layer.
    """
    order = queries.get_order(order_id)
    tables_used = ["orders"]

    if not order:
        return {"ok": False, "reason": "not_found", "order": None, "tables_used": tables_used}

    authorized = permissions.is_authorized_for_order(
        order, provided_email, mode, customer_email_lookup=_customer_email_lookup
    )
    tables_used.append("customers")

    if not authorized:
        return {"ok": False, "reason": "unauthorized", "order": None, "tables_used": tables_used}

    safe_order = {
        "order_id": order["order_id"],
        "product": order["product"],
        "quantity": order["quantity"],
        "order_status": order["order_status"],
        "amount": order["amount"],
        "delivery_date": order["delivery_date"],
    }
    return {"ok": True, "reason": "authorized", "order": safe_order, "tables_used": tables_used}
