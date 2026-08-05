"""
app/main.py

FastAPI entry point. Ensures the database is seeded, constructs ONE
QwenClient and ONE SupportAgent at startup (never per-request), and
mounts the API routes.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
or:
    python -m app.main
"""
from fastapi import FastAPI

from app.config import settings
from app.database.seed import ensure_seeded
from app.services.qwen_client import QwenClient
from app.chatbot.agent import SupportAgent
from app.api import routes

ensure_seeded()

app = FastAPI(title="Acme Enterprise Support Assistant", version="2.0.0")

_model_client = QwenClient()
_agent = SupportAgent(model_client=_model_client, mode=settings.TARGET_MODE)
routes.bind_agent(_agent)

app.include_router(routes.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
