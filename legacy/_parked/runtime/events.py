# samos/runtime/events.py
import os, json, time
from datetime import datetime
from typing import Any, Dict, Optional, Iterable, ContextManager
from contextlib import contextmanager

DEFAULT_EVENTS_PATH = ".samos/events.jsonl"

class EventLogger:
    """
    Minimal JSONL event logger.
    Usage:
        logger = EventLogger()
        logger.log("skill.ok", skill="SummarizeSkill", latency_ms=42)
        with logger.span("llm", provider="openai", model="gpt-4o-mini") as ev:
            ... do work ...
            ev["tokens_in"] = 120
    """
    def __init__(self, path: str = DEFAULT_EVENTS_PATH) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def log(self, event: str, **fields: Any) -> None:
        record = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event,
            **fields,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @contextmanager
    def span(self, event_prefix: str, **fields: Any) -> ContextManager[Dict[str, Any]]:
        """
        Context manager that measures latency and writes <event_prefix>.ok or <event_prefix>.fail
        """
        start = time.perf_counter()
        data: Dict[str, Any] = dict(fields)
        try:
            yield data
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.log(f"{event_prefix}.ok", latency_ms=latency_ms, **data)
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.log(f"{event_prefix}.fail", latency_ms=latency_ms,
                     error=str(e), error_type=type(e).__name__, **data)
            raise
