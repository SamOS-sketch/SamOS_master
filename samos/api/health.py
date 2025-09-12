# samos/api/health.py
from fastapi import APIRouter
from typing import Any, Dict

from samos.core.config import get_storage_dir
from samos.runtime.event_logger import EventLogger
from samos.runtime.heartbeat import run_heartbeat

router = APIRouter(tags=["health"])

def _get_event_logger() -> EventLogger:
    storage_path = str(get_storage_dir())
    events_path = f"{storage_path}/events/events.jsonl"
    return EventLogger(events_path)

@router.get("/health")
def health() -> Dict[str, Any]:
    """
    Runs the heartbeat checks and returns the payload.
    Always 200; see 'status' field for heartbeat.ok/heartbeat.corrected/heartbeat.failed.
    """
    logger = _get_event_logger()
    payload = run_heartbeat(config=None, event_logger=logger)
    return payload
