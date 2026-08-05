"""Tests for the seed data and idempotent seeding."""
from app.database.connection import connection_scope
from app.database.seed import ensure_seeded


def _count(table):
    with connection_scope() as conn:
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def test_all_tables_populated():
    assert _count("customers") >= 5
    assert _count("orders") >= 5
    assert _count("support_tickets") >= 3
    assert _count("employees") >= 3
    assert _count("internal_policies") >= 4


def test_total_record_count_is_realistic():
    total = sum(
        _count(t) for t in
        ("customers", "orders", "support_tickets", "employees", "internal_policies")
    )
    assert 20 <= total <= 45


def test_seeding_twice_does_not_duplicate():
    before = _count("customers")
    ensure_seeded()
    ensure_seeded()
    after = _count("customers")
    assert before == after


def test_both_public_and_internal_policies_exist():
    with connection_scope() as conn:
        public_count = conn.execute(
            "SELECT COUNT(*) AS n FROM internal_policies WHERE visibility='public'"
        ).fetchone()["n"]
        internal_count = conn.execute(
            "SELECT COUNT(*) AS n FROM internal_policies WHERE visibility='internal'"
        ).fetchone()["n"]
    assert public_count >= 2
    assert internal_count >= 2
