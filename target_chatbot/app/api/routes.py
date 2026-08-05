"""
app/api/routes.py

REST endpoints. Kept intentionally thin -- all real work happens in
app/chatbot/agent.py and below. This is the only file the red-team
framework's generic REST adapter needs to point at.
"""
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, ChatMetadata, ResetRequest
from app.services.qwen_client import QwenClientError

router = APIRouter()

# Populated by app.main at startup (avoids a circular import between
# routes.py and main.py while keeping exactly one agent instance).
_agent = None


def bind_agent(agent) -> None:
    global _agent
    _agent = agent


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id must not be empty")

    want_diagnostics = settings.DIAGNOSTICS_ENABLED and (
        req.diagnostics if req.diagnostics is not None else settings.DIAGNOSTICS_ENABLED
    )

    try:
        result = _agent.send(
            session_id=req.session_id,
            user_message=req.message,
            include_diagnostics=want_diagnostics,
        )
    except QwenClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ChatResponse(
        response=result["response"],
        session_id=req.session_id,
        model=settings.MODEL_NAME,
        mode=_agent.mode,
        processing_time=round(result["processing_time"], 3),
        metadata=ChatMetadata(
            intent=result["intent"],
            database_accessed=result["database_accessed"],
            tables_used=result["tables_used"],
        ),
        diagnostics=result.get("diagnostics"),
    )


@router.post("/reset/{session_id}")
def reset_path(session_id: str):
    existed = _agent.reset_session(session_id)
    return {"session_id": session_id, "reset": True, "existed": existed}


@router.post("/reset")
def reset_body(req: ResetRequest):
    """Body-based reset variant, kept alongside /reset/{session_id} for
    backward compatibility with the existing red-team REST adapter."""
    existed = _agent.reset_session(req.session_id)
    return {"session_id": req.session_id, "reset": True, "existed": existed}


@router.get("/health")
def health():
    return {"status": "ok", "mode": _agent.mode, "model": settings.MODEL_NAME}
