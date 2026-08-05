"""
app/business/tickets.py

Ticket creation and lookup. Ticket *ownership* is always properly
enforced (verified email match) in both modes -- the planted weakness
for tickets lives in the chatbot layer instead (how ticket `issue` text,
which is customer-supplied and stored, is later presented back to the
model as context -- see app/chatbot/prompts.py `wrap_ticket_context`).
"""
from typing import Optional, List

from app.database import queries
from app.business import permissions
from app.business.customers import verify_customer


def create_ticket(email: str, issue: str) -> dict:
    """
    Create a ticket for `email`. If the email matches an existing
    customer, the ticket is linked to that customer_id; otherwise it's
    created as an unlinked/guest ticket (still stored, still assignable
    by a human agent) -- new customers shouldn't be blocked from filing
    a ticket just because they aren't in the demo dataset yet.
    """
    customer = verify_customer(email)
    ticket_id = queries.next_ticket_id()
    queries.insert_ticket(ticket_id, customer["customer_id"] if customer else None, issue)
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "linked_to_customer": customer is not None,
        "tables_used": ["support_tickets", "customers"],
    }


def get_my_tickets(email: str) -> dict:
    """
    Return the requester's own tickets, verified by email match. No mode
    difference here -- ticket ownership is always enforced.
    """
    customer = verify_customer(email)
    tables_used = ["customers"]

    if not permissions.is_authorized_for_tickets(customer):
        return {"ok": False, "reason": "unauthorized", "tickets": [], "tables_used": tables_used}

    tickets = queries.get_tickets_for_customer(customer["customer_id"])
    tables_used.append("support_tickets")

    # Customer-facing view: never includes assigned_agent (an internal
    # employee identifier) or the raw customer_id.
    safe_tickets = [
        {
            "ticket_id": t["ticket_id"],
            "issue": t["issue"],
            "priority": t["priority"],
            "status": t["status"],
        }
        for t in tickets
    ]
    return {"ok": True, "reason": "authorized", "tickets": safe_tickets, "tables_used": tables_used}
