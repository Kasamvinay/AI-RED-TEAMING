"""
app/config/settings.py

Single place all configuration is read from. Nothing in this project
imports environment variables directly anywhere else -- if you need a
new tunable, add it here.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Target mode ------------------------------------------------------
# "vulnerable" or "hardened". Same model, same business data, same
# customer-support functionality. What changes is enforcement of a small,
# realistic set of security-relevant behaviors documented in
# app/business/permissions.py and app/chatbot/prompts.py -- NOT a toy
# keyword switch. This lets the same red-team framework run twice and
# compare attack-success/leak rates before vs after fixing the planted
# weaknesses.
TARGET_MODE = os.getenv("TARGET_MODE", "vulnerable").strip().lower()
if TARGET_MODE not in ("vulnerable", "hardened"):
    raise ValueError(f"TARGET_MODE must be 'vulnerable' or 'hardened', got {TARGET_MODE!r}")

# --- Model serving ------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b-instruct-q4_K_M")
TEMPERATURE = _float("TEMPERATURE", 0.4)
MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 256)
REQUEST_TIMEOUT_SECONDS = _int("REQUEST_TIMEOUT_SECONDS", 120)

# --- Conversation / resource limits --------------------------------------
MAX_HISTORY_TURNS = _int("MAX_HISTORY_TURNS", 6)

# --- Database -------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "acme_support.sqlite3"))

# --- Diagnostics ------------------------------------------------------------
DIAGNOSTICS_ENABLED = _bool("DIAGNOSTICS_ENABLED", True)

# --- Server -----------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = _int("PORT", 8000)

# --- Logging ------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
