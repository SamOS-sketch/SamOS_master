from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# -----------------------------
# Existing API Schemas (kept)
# -----------------------------


class SessionStartResponse(BaseModel):
    session_id: str
    mode: str


class ModeSetRequest(BaseModel):
    session_id: str
    mode: str


class ModeGetResponse(BaseModel):
    session_id: str
    mode: str


class MemoryPutRequest(BaseModel):
    session_id: str
    key: str
    value: str
    meta: Optional[Dict[str, Any]] = None


class MemoryGetRequest(BaseModel):
    session_id: str
    key: str


class MemoryItem(BaseModel):
    key: str
    value: str
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryListResponse(BaseModel):
    items: List[MemoryItem]


class EMMCreateRequest(BaseModel):
    session_id: str
    type: str = Field(..., description="EMM type, e.g., Spark, OneBounce")
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class EMMItem(BaseModel):
    id: int
    type: str
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: str


class EMMListResponse(BaseModel):
    items: List[EMMItem]


class ImageGenerateRequest(BaseModel):
    session_id: str
    prompt: str


class ImageGenerateResponse(BaseModel):
    image_id: str
    url: str
    provider: str
    reference_used: str
    status: str = "ok"
    meta: Optional[Dict[str, Any]] = None


# -----------------------------
# Phase 7 – New Schemas
# (API-side representations)
# -----------------------------


# Metrics (API schema — not the DB tables)
class MetricsCounterModel(BaseModel):
    key: str
    value: int
    updated_at: str


class MetricsBucketModel(BaseModel):
    metric: str
    period: Literal["hour", "day"]
    bucket_start: str
    value: int


class MetricsSnapshot(BaseModel):
    counters: List[MetricsCounterModel] = []
    buckets: List[MetricsBucketModel] = []


# Snapshot item types
class SessionSnapshot(BaseModel):
    id: str
    mode: str
    created_at: Optional[str] = None
    last_active: Optional[str] = None


class MemorySnapshot(BaseModel):
    id: Optional[str] = None
    session_id: str
    scope: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EMMSnapshot(BaseModel):
    id: Optional[str] = None
    session_id: str
    tag: Optional[str] = None
    type: Optional[str] = None  # allow older snapshots
    message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ImageSnapshot(BaseModel):
    id: Optional[str] = None
    session_id: str
    url: str
    prompt: Optional[str] = None
    reference_used: Optional[str] = None
    provider: Optional[str] = None
    created_at: Optional[str] = None


class EventSnapshot(BaseModel):
    id: Optional[str] = None
    session_id: Optional[str] = None
    type: str
    ts: str
    meta: Optional[Dict[str, Any]] = None


# Full snapshot payload
class SnapshotResponse(BaseModel):
    schema_version: int = 3
    created_at: str
    app_version: Optional[str] = None

    sessions: List[SessionSnapshot] = []
    memories: List[MemorySnapshot] = []
    emms: List[EMMSnapshot] = []
    images: List[ImageSnapshot] = []
    events: List[EventSnapshot] = []

    metrics: Optional[MetricsSnapshot] = None


# Convenience request model if you prefer body-validated restore
class RestoreRequest(BaseModel):
    snapshot: SnapshotResponse
    mode: Literal["replace", "merge"] = "replace"
