# samos/runtime/heartbeat.py
from __future__ import annotations
import json, os, sys, tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

# Existing modules from earlier phases:
from samos.core.config import get_storage_dir
from samos.runtime.event_logger import EventLogger  # appends JSONL to events/events.jsonl


HEARTBEAT_EVENT_OK = "heartbeat.ok"
HEARTBEAT_EVENT_CORRECTED = "heartbeat.corrected"
HEARTBEAT_EVENT_FAILED = "heartbeat.failed"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_str_path(p: Any) -> str:
    """Return a string path for Path/str-like values."""
    if isinstance(p, Path):
        return str(p)
    return str(p)


def _json_safe(obj: Any) -> Any:
    """
    Recursively convert objects to JSON-safe types.
    - Path -> str
    - set/tuple -> list
    - dict keys -> str
    """
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    return obj


def _check_soulprint(storage_path: str) -> Dict[str, Any]:
    soulprint_path = os.path.join(storage_path, "memory", "soulprint.json")
    result: Dict[str, Any] = {"present": False}
    if not os.path.exists(soulprint_path):
        return result

    try:
        with open(soulprint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version")
        identity_name = (data.get("identity") or {}).get("name")
        result.update({"present": True, "version": version, "identity_name": identity_name})
    except Exception:
        # file exists but unreadable/invalid
        result.update({"present": False, "invalid": True})
    return result


def _ensure_storage_dirs(storage_path: str) -> List[str]:
    """Ensure required subdirs exist. Return list of corrections applied."""
    corrections: List[str] = []
    required = [
        storage_path,
        os.path.join(storage_path, "memory"),
        os.path.join(storage_path, "events"),
        os.path.join(storage_path, "images"),
        os.path.join(storage_path, "images", "reference"),
        os.path.join(storage_path, "outputs"),
    ]
    for p in required:
        if not os.path.exists(p):
            os.makedirs(p, exist_ok=True)
            corrections.append(f"mkdir:{os.path.relpath(p, storage_path)}")
    return corrections


def _check_writable(storage_path: str) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=storage_path, delete=True) as _:
            pass
        return True
    except Exception:
        return False


def _find_reference_image(storage_path: str) -> Dict[str, Any]:
    ref_dir = os.path.join(storage_path, "images", "reference")
    candidates = [
        "ReferenceImageAlpha.jpg",
        "ReferenceImageAlpha.jpeg",
        "ReferenceImageAlpha.png",
        "ReferenceImageAlpha.webp",
    ]
    for name in candidates:
        fp = os.path.join(ref_dir, name)
        if os.path.exists(fp):
            return {"present": True, "filename": name}
    return {"present": False}


def _emit_event(event_logger: EventLogger, events_path: str, status: str, payload: Dict[str, Any]) -> None:
    """
    Try several common EventLogger method names; if none exist, write JSONL directly.
    Ensures the record is JSON-serializable (converts Path objects to str, etc.).
    """
    # Normalize payload for JSON
    payload = _json_safe(payload)

    record = {"type": status, "ts": _iso_now()}
    if isinstance(payload, dict):
        record.update(payload)
        record["type"] = status
        if "ts" not in record:
            record["ts"] = _iso_now()

    # Try likely logger methods
    candidates = [
        ("log", (status, record), {}),        # some versions accept (type, payload)
        ("emit", (record,), {}),
        ("write", (record,), {}),
        ("append", (record,), {}),
        ("record", (record,), {}),
        ("write_event", (record,), {}),
    ]
    for name, args, kwargs in candidates:
        if hasattr(event_logger, name):
            try:
                getattr(event_logger, name)(*args, **kwargs)
                return
            except Exception:
                pass  # fall through

    # Fallback: write JSONL directly
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_heartbeat(config: Optional[Dict[str, Any]], event_logger: EventLogger) -> Dict[str, Any]:
    # Resolve storage path (may be Path; normalize to str)
    storage_dir = get_storage_dir()
    storage_path = _to_str_path(storage_dir)

    corrections = _ensure_storage_dirs(storage_path)
    storage_writable = _check_writable(storage_path)
    soulprint = _check_soulprint(storage_path)
    reference_image = _find_reference_image(storage_path)

    reasons: List[str] = []
    if not storage_writable:
        reasons.append("storage_not_writable")
    if not soulprint.get("present"):
        reasons.append("soulprint_missing" if not soulprint.get("invalid") else "soulprint_invalid")
    if not reference_image.get("present"):
        reasons.append("reference_image_missing")

    if reasons:
        status = HEARTBEAT_EVENT_FAILED
    elif corrections:
        status = HEARTBEAT_EVENT_CORRECTED
    else:
        status = HEARTBEAT_EVENT_OK

    payload: Dict[str, Any] = {
        "status": status,
        "storage": {"path": storage_path, "writable": storage_writable},
        "soulprint": soulprint,
        "reference_image": reference_image,
        "corrections_applied": corrections,
        "reasons": reasons if reasons else [],
    }

    events_path = os.path.join(storage_path, "events", "events.jsonl")
    _emit_event(event_logger, events_path, status, payload)

    return payload


def main() -> int:
    # Minimal CLI runner
    storage_dir = get_storage_dir()
    storage_path = _to_str_path(storage_dir)
    events_path = os.path.join(storage_path, "events", "events.jsonl")
    logger = EventLogger(events_path)

    result = run_heartbeat(config=None, event_logger=logger)
    print(json.dumps(_json_safe(result), separators=(",", ":")))
    return 0 if result["status"] in (HEARTBEAT_EVENT_OK, HEARTBEAT_EVENT_CORRECTED) else 1


if __name__ == "__main__":
    sys.exit(main())
