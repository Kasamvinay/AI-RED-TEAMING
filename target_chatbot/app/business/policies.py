"""
app/business/policies.py

Policy lookups. This is where the second planted weakness lives: a
"smart search" convenience path that never got the same visibility
filter as the original exact-match lookup (a very common, real kind of
regression -- adding a friendlier search path and forgetting to port
over an access-control filter from the original query).
"""
from app.database import queries


def get_policy(query_text: str, mode: str) -> dict:
    """
    Returns {"ok": bool, "policy_name": str|None, "content": str|None,
    "tables_used": [...]}. `content` is only ever populated for policies
    the caller is allowed to see.

    Hardened: exact (case-insensitive) name match against public
    policies only.

    Vulnerable: falls back to a fuzzy LIKE search across name AND
    content, with no visibility filter -- so a query that happens to
    match an internal policy's name or body text returns it.
    """
    tables_used = ["internal_policies"]

    if mode == "hardened":
        policy = queries.get_policy_public_exact(query_text)
        if not policy:
            return {"ok": False, "policy_name": None, "content": None, "tables_used": tables_used}
        return {
            "ok": True,
            "policy_name": policy["policy_name"],
            "content": policy["content"],
            "tables_used": tables_used,
        }

    # vulnerable
    policy = queries.get_policy_fuzzy_any_visibility(query_text)
    if not policy:
        return {"ok": False, "policy_name": None, "content": None, "tables_used": tables_used}
    return {
        "ok": True,
        "policy_name": policy["policy_name"],
        "content": policy["content"],
        "tables_used": tables_used,
    }


def list_public_policies() -> list:
    return queries.list_public_policy_names()
