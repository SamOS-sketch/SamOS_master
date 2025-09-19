# samos/api/routes_sessions.py
from __future__ import annotations

import json
import uuid
from typing import Optional, Dict

from fastapi import APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from samos.api.db import SessionLocal, Event as DBEvent

router = APIRouter()


def _emit(db: Session, session_id: Optional[str], kind: str, message: str, meta: Dict):
    """Soft-fail event writer: never crash if events table isn't ready."""
    try:
        evt = DBEvent(
            session_id=session_id,
            kind=kind,
            message=message,
            meta_json=json.dumps(meta or {}),
        )
        db.add(evt)
        db.commit()
    except SQLAlchemyError:
        db.rollback()


@router.post("/session/start")
def session_start():
    """
    Minimal V1 session start.
    - Generates a UUID4 session_id.
    - Soft-logs an event (if events table exists).
    - Returns the session_id (no DB row required for V1).
    """
    sid = str(uuid.uuid4())
    with SessionLocal() as db:
        _emit(db, sid, "session.start", "begin", {})
    return {"session_id": sid}
