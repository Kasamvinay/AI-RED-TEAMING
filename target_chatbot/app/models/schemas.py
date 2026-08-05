"""
app/models/schemas.py

Pydantic request/response models for the REST API. Kept separate from
app/database (which has its own, unrelated notion of "schema" -- the SQL
DDL).
"""
from typing import Optional, List

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    diagnostics: Optional[bool] = None


class ChatMetadata(BaseModel):
    intent: str
    database_accessed: bool
    tables_used: List[str] = []


class ChatResponse(BaseModel):
    response: str
    session_id: str
    model: str
    mode: str
    processing_time: float
    metadata: ChatMetadata
    diagnostics: Optional[dict] = None


class ResetRequest(BaseModel):
    session_id: str
