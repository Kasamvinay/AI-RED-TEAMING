"""
app/utils/logging_setup.py

One shared logger configuration so every layer (API, business logic,
database) logs consistently. Business-logic and database calls log at
DEBUG/INFO; nothing here ever logs a protected value in cleartext (see
each business module -- logs reference IDs/booleans, not secret content).
"""
import logging

from app.config import settings

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        )
        _configured = True
    return logging.getLogger(name)
