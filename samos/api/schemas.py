# samos/api/schemas.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from typing_extensions import Literal
from pydantic import BaseModel, Field, ConfigDict


# ---------- Core envelopes ----------
class ErrorObject(BaseModel):
    code: str = Field(..., description="Machine-readable code, e.g. VALIDATION_ERROR")
    message: str = Field(..., description="Human-readable message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured context")


class ErrorEnvelope(BaseModel):
    ok: Literal[False] = False
    error: ErrorObject
    request_id: str


class OkEnvelope(BaseModel):
    ok: Literal[True] = True
    data: Any


class ListEnvelope(BaseModel):
    ok: Literal[True] = True
    data: List[Any]
    next_cursor: Optional[str] = Field(default=None, description="Opaque cursor for pagination")


# ---------- Image models ----------
class ImageMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2: ORM mode

    # ID can be numeric for successful rows OR hex string for failed rows
    id: str
    session_id: str
    provider: str
    status: str
    url: Optional[str] = None
    size: Optional[str] = None
    # FIX: ref_used stored as bool in DB → must be bool here
    ref_used: Optional[bool] = None
    drift_score: Optional[float] = None
    created_at: datetime
    file_exists: Optional[bool] = Field(default=None, description="True when local file is present")
    file_path: Optional[str] = Field(default=None, description="Absolute local path if available (dev only)")


# ---------- Event models ----------
class EventEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    kind: str
    payload: Dict[str, Any]
    created_at: datetime


# ---------- Metrics model (read-only helper) ----------
class MetricsSnapshot(BaseModel):
    images_generated: int
    images_failed: int
    requests_by_path: Dict[str, int]
    captured_at: datetime = Field(default_factory=datetime.utcnow)
