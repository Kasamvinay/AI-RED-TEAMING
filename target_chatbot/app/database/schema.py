"""
app/database/schema.py

DDL for the fictional Acme Inc. support database. Five tables:
customers, orders, support_tickets, employees (sensitive, no legitimate
read path from the chatbot at all), and internal_policies (mixed
public/internal visibility).
"""

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id     INTEGER PRIMARY KEY,
        name            TEXT NOT NULL,
        email           TEXT NOT NULL UNIQUE,
        phone           TEXT NOT NULL,
        membership_level TEXT NOT NULL,
        reward_points   INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id        TEXT PRIMARY KEY,
        customer_id     INTEGER NOT NULL,
        product         TEXT NOT NULL,
        quantity        INTEGER NOT NULL,
        order_status    TEXT NOT NULL,
        amount          REAL NOT NULL,
        delivery_date   TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS support_tickets (
        ticket_id       TEXT PRIMARY KEY,
        customer_id     INTEGER,
        issue           TEXT NOT NULL,
        priority        TEXT NOT NULL,
        assigned_agent  TEXT,
        status          TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
        FOREIGN KEY (assigned_agent) REFERENCES employees(employee_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS employees (
        employee_id     TEXT PRIMARY KEY,
        employee_name   TEXT NOT NULL,
        designation     TEXT NOT NULL,
        department      TEXT NOT NULL,
        internal_email  TEXT NOT NULL,
        employee_role   TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS internal_policies (
        policy_id       INTEGER PRIMARY KEY,
        policy_name     TEXT NOT NULL,
        content         TEXT NOT NULL,
        visibility      TEXT NOT NULL CHECK (visibility IN ('public', 'internal'))
    )
    """,
]


def create_schema(conn):
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
