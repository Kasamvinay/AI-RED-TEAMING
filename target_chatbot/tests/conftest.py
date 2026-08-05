"""
tests/conftest.py

Must set DB_PATH (and other env vars) BEFORE any `app.*` module is
imported anywhere in the test suite, since app/config/settings.py reads
them at import time. pytest imports conftest.py first, and this runs at
module load time (not inside a fixture), so it always wins the race.
"""
import os
import sys
import tempfile
from pathlib import Path

_tmp_dir = tempfile.mkdtemp(prefix="acme_test_db_")
os.environ["DB_PATH"] = str(Path(_tmp_dir) / "test_acme_support.sqlite3")
os.environ.setdefault("TARGET_MODE", "vulnerable")
os.environ.setdefault("DIAGNOSTICS_ENABLED", "true")

# Make the project root importable as `app` / `security` regardless of
# where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.database.seed import ensure_seeded


@pytest.fixture(scope="session", autouse=True)
def _seeded_db():
    ensure_seeded()
    yield
