from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json
import threading
from typing import Any, Dict, Optional

# SSD-aware base path
from samos.core.config import STORAGE_DIR

EVENTS_PATH: Path = STORAGE_DIR / "events"
LOG_FILE: Path = EVENTS_PATH / "events.jsonl"

_lock = threading.Lock()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def log_event(event: str, data: Optional[Dict[str, Any]] = None, level: str = "info") -> Path:
    """
    Append a JSON line to the events log on the SSD.
    Always includes storage.path metadata so we can prove where we're writing.
    """
    record: Dict[str, Any] = {
        "ts": _now_iso(),
        "event": event,
        "level": level,
        "storage.path": str(EVENTS_PATH),
    }
    if data:
        record.update(data)

    EVENTS_PATH.mkdir(parents=True, exist_ok=True)

    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return LOG_FILE

class EventLogger:
    def __init__(self, log_path: Optional[Path] = None):
        self.path = log_path or LOG_FILE

    def write(self, event: str, data: Optional[Dict[str, Any]] = None, level: str = "info") -> Path:
        dirpath = self.path.parent
        dirpath.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _now_iso(),
            "event": event,
            "level": level,
            "storage.path": str(dirpath),
        }
        if data:
            record.update(data)
        line = json.dumps(record, ensure_ascii=False)
        with _lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return self.path
