import json
from typing import Dict, Optional

from ..db import Event, SessionLocal


def record_event(
    kind: str,
    message: str,
    session_id: Optional[str] = None,
    meta: Optional[Dict] = None,
) -> None:
    """Write a single observability event to the database."""
    db = SessionLocal()
    try:
        e = Event(
            session_id=session_id,
            kind=kind,
            message=(message or "")[:255],
            meta_json=json.dumps(meta or {}),
        )
        db.add(e)
        db.commit()
    finally:
        db.close()
