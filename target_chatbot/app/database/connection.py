"""
app/database/connection.py

Thin SQLite connection helper. This is the ONLY module that opens a
database connection. Business-logic modules call functions in
app/database/queries.py, which use this -- the chatbot/agent layer never
touches the database directly, matching the "AI model should NOT
directly query the database" requirement.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


def get_connection() -> sqlite3.Connection:
    # sqlite3 does not create parent directories -- ensure DB_PATH's
    # folder exists on first use (e.g. a fresh checkout's ./data/ dir).
    db_path = Path(settings.DB_PATH)
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection_scope():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
