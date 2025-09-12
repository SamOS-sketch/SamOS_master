# samos/runtime/pulse.py
import os, time, psutil, asyncio, json
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any

from samos.core.config import get_storage_dir
from samos.runtime.event_logger import EventLogger
from samos.api.db import SessionLocal
from sqlalchemy import text as sql_text  # <-- for DB probe

PULSE_INTERVAL_SECS     = int(os.getenv("PULSE_INTERVAL_SECS", "30"))
PULSE_ALERT_WINDOW_SECS = int(os.getenv("PULSE_ALERT_WINDOW_SECS", "300"))
PULSE_ALERT_FAILRATE    = float(os.getenv("PULSE_ALERT_FAILRATE", "0.2"))

_start_time = time.time()
_fail_ts = deque(maxlen=10_000)  # timestamps of provider failures

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _uptime_seconds() -> int:
    return int(time.time() - _start_time)

def _db_ok() -> bool:
    db = None
    try:
        db = SessionLocal()
        db.execute(sql_text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        try:
            if db:
                db.close()
        except Exception:
            pass

def note_provider_failure() -> None:
    _fail_ts.append(time.time())

def _failure_rate_window(now: float) -> float:
    cutoff = now - PULSE_ALERT_WINDOW_SECS
    while _fail_ts and _fail_ts[0] < cutoff:
        _fail_ts.popleft()
    fails = len(_fail_ts)
    expected_ticks = max(1, PULSE_ALERT_WINDOW_SECS // max(1, PULSE_INTERVAL_SECS))
    return fails / expected_ticks

def collect_pulse_metrics() -> Dict[str, Any]:
    mem = psutil.Process().memory_info()
    now = time.time()
    return {
        "ts": _iso_now(),
        "uptime_seconds": _uptime_seconds(),
        "memory_rss": mem.rss,
        "memory_vms": mem.vms,
        "db_ok": _db_ok(),
        "provider_failures_window": len(_fail_ts),
        "provider_fail_rate": round(_failure_rate_window(now), 3),
        "alert_window_secs": PULSE_ALERT_WINDOW_SECS,
        "alert_failrate_threshold": PULSE_ALERT_FAILRATE,
    }

async def pulse_loop():
    storage_path = str(get_storage_dir())
    events_path = os.path.join(storage_path, "events", "events.jsonl")
    logger = EventLogger(events_path)

    while True:
        metrics = collect_pulse_metrics()
        tick = {"type": "pulse.tick", **metrics}

        # Write tick
        try:
            if hasattr(logger, "emit"):
                logger.emit(tick)
            elif hasattr(logger, "write"):
                logger.write(tick)
            else:
                os.makedirs(os.path.dirname(events_path), exist_ok=True)
                with open(events_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(tick) + "\n")
        except Exception:
            pass

        # Alerts
        if (not metrics.get("db_ok")) or (metrics.get("provider_fail_rate", 0.0) > PULSE_ALERT_FAILRATE):
            alert = {
                "type": "pulse.alert",
                "ts": _iso_now(),
                "db_ok": metrics.get("db_ok"),
                "provider_fail_rate": metrics.get("provider_fail_rate"),
                "provider_failures_window": metrics.get("provider_failures_window"),
                "threshold": PULSE_ALERT_FAILRATE,
                "window_secs": PULSE_ALERT_WINDOW_SECS,
            }
            try:
                if hasattr(logger, "emit"):
                    logger.emit(alert)
                elif hasattr(logger, "write"):
                    logger.write(alert)
                else:
                    with open(events_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(alert) + "\n")
            except Exception:
                pass

        await asyncio.sleep(PULSE_INTERVAL_SECS)
