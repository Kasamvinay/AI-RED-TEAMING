"""
app/database/queries.py

Raw, parameterized SQL access -- one function per data need. Deliberately
contains NO authorization or policy logic; that all lives one layer up in
app/business/*.py. This separation is what lets us point at exactly where
a permission check does or doesn't happen.

Every query is parameterized (no string-formatted SQL) to avoid SQL
injection as an unrelated, uninteresting vulnerability class -- the
experiment is about prompt injection / business-logic authorization, not
SQL injection.
"""
from typing import Optional, List

from app.database.connection import connection_scope


def find_customer_by_email(email: str) -> Optional[dict]:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE lower(email) = lower(?)", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_order(order_id: str) -> Optional[dict]:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None


def get_tickets_for_customer(customer_id: int) -> List[dict]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM support_tickets WHERE customer_id = ? ORDER BY ticket_id",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_ticket(ticket_id: str) -> Optional[dict]:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return dict(row) if row else None


def insert_ticket(ticket_id: str, customer_id: Optional[int], issue: str) -> None:
    with connection_scope() as conn:
        conn.execute(
            "INSERT INTO support_tickets (ticket_id, customer_id, issue, priority, assigned_agent, status) "
            "VALUES (?, ?, ?, 'Medium', NULL, 'Open')",
            (ticket_id, customer_id, issue),
        )


def next_ticket_id() -> str:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT ticket_id FROM support_tickets ORDER BY ticket_id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "TCK-2001"
        last_num = int(row["ticket_id"].split("-")[1])
        return f"TCK-{last_num + 1}"


def get_policy_public_exact(policy_name: str) -> Optional[dict]:
    """Hardened path: exact (case-insensitive) name match, public only."""
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM internal_policies WHERE lower(policy_name) = lower(?) AND visibility = 'public'",
            (policy_name,),
        ).fetchone()
        return dict(row) if row else None


def get_policy_fuzzy_any_visibility(query_text: str) -> Optional[dict]:
    """
    Vulnerable path: a loose LIKE match across ALL policies, regardless of
    visibility. This mirrors a real, common implementation bug: a
    "smart search" was added for convenience and the visibility filter
    from the original exact-match query was never carried over to it.
    """
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM internal_policies WHERE policy_name LIKE ? OR content LIKE ? LIMIT 1",
            (f"%{query_text}%", f"%{query_text}%"),
        ).fetchone()
        return dict(row) if row else None


def list_public_policy_names() -> List[str]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT policy_name FROM internal_policies WHERE visibility = 'public' ORDER BY policy_name"
        ).fetchall()
        return [r["policy_name"] for r in rows]
