# samos/api/routes_events.py
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from samos.api.db import SessionLocal, Event as DBEvent
from samos.api.schemas import EventEntry
from samos.api.utils.http import ok_list, fail

print("[SamOS] routes_events vA10-0 loaded")
router = APIRouter(prefix="/events", tags=["events"])


# ---------- cursor helpers ----------
# Cursor format (base64): "<iso8601>|<id>"
def _encode_cursor(ts: datetime, id_: int) -> str:
    raw = f"{ts.isoformat()}|{id_}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cur: str) -> Tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(cur.encode("ascii")).decode("utf-8")
    ts_s, id_s = raw.split("|", 1)
    return (datetime.fromisoformat(ts_s), int(id_s))


# ---------- core query ----------
def _query_events(
    session_id: Optional[str],
    kinds: Optional[List[str]],
    limit: int,
    cursor: Optional[str],
) -> Tuple[List[EventEntry], Optional[str]]:
    db = SessionLocal()
    try:
        q = db.query(DBEvent)
        if session_id:
            q = q.filter(DBEvent.session_id == session_id)
        if kinds:
            q = q.filter(DBEvent.kind.in_(kinds))

        # paging: if cursor present, fetch items *before* that (ts, id)
        if cursor:
            ts, last_id = _decode_cursor(cursor)
            q = q.filter(
                (DBEvent.ts < ts) |
                ((DBEvent.ts == ts) & (DBEvent.id < last_id))
            )

        q = q.order_by(DBEvent.ts.desc(), DBEvent.id.desc()).limit(max(1, min(limit, 200)))
        rows = q.all()

        items: List[EventEntry] = []
        for r in rows:
            # Payload from meta_json; include message for convenience
            try:
                payload = json.loads(r.meta_json or "{}")
            except Exception:
                payload = {}
            if getattr(r, "message", None):
                payload.setdefault("_message", r.message)

            items.append(
                EventEntry(
                    id=r.id,
                    session_id=r.session_id,
                    kind=r.kind,
                    payload=payload,
                    created_at=r.ts,  # map DB ts -> schema created_at
                )
            )

        next_cursor = None
        if rows:
            tail = rows[-1]
            next_cursor = _encode_cursor(tail.ts, tail.id)

        return items, next_cursor
    finally:
        db.close()


# ---------- JSON API (moved to /events/list to avoid conflict with main.py) ----------
@router.get("/list")
def list_events(
    request: Request,
    session_id: Optional[str] = None,
    kinds: Optional[str] = None,  # comma-separated
    limit: int = 50,
    cursor: Optional[str] = None,
):
    try:
        kinds_list = [k.strip() for k in kinds.split(",")] if kinds else None
        items, next_cursor = _query_events(session_id, kinds_list, limit, cursor)
        return ok_list(items, next_cursor=next_cursor)
    except Exception as e:
        return fail("EVENTS_ERROR", f"Failed to list events: {e}", request=request, status_code=500)


# ---------- Minimal HTML view (dev only) ----------
@router.get("/view")
def view_events(
    request: Request,
    session_id: Optional[str] = None,
    kinds: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
):
    if os.getenv("SAMOS_ENV", "dev") != "dev":
        return fail("FORBIDDEN", "HTML view only available in dev", request=request, status_code=403)

    kinds_list = [k.strip() for k in kinds.split(",")] if kinds else None
    items, next_cursor = _query_events(session_id, kinds_list, limit, cursor)

    # very small HTML (no templates) for quick debugging
    rows_html = []
    for it in items:
        payload = json.dumps(it.payload, ensure_ascii=False)
        rows_html.append(
            f"<tr>"
            f"<td>{it.id}</td>"
            f"<td>{it.created_at}</td>"
            f"<td>{it.session_id}</td>"
            f"<td>{it.kind}</td>"
            f"<td style='white-space:pre-wrap'>{payload}</td>"
            f"</tr>"
        )
    next_link = ""
    if next_cursor:
        from urllib.parse import urlencode
        qs = urlencode({k: v for k, v in {
            "session_id": session_id or "",
            "kinds": kinds or "",
            "limit": str(limit),
            "cursor": next_cursor
        }.items() if v})
        next_link = f"<a href='/events/view?{qs}'>Next →</a>"

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>SamOS Events</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; padding: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
th {{ background: #f5f5f5; text-align: left; }}
code {{ white-space: pre-wrap; }}
.controls {{ margin-bottom: 12px; }}
</style>
</head>
<body>
  <h1>SamOS Events</h1>
  <div class="controls">
    <form method="get" action="/events/view">
      <label>Session ID: <input name="session_id" value="{session_id or ''}" style="width:320px" /></label>
      <label style="margin-left:12px">Kinds: <input name="kinds" value="{kinds or ''}" placeholder="comma-separated" style="width:260px" /></label>
      <label style="margin-left:12px">Limit: <input name="limit" value="{limit}" size="4" /></label>
      <button type="submit">Apply</button>
    </form>
  </div>
  <table>
    <thead><tr><th>ID</th><th>Time</th><th>Session</th><th>Kind</th><th>Payload</th></tr></thead>
    <tbody>
      {''.join(rows_html) or '<tr><td colspan="5">No events</td></tr>'}
    </tbody>
  </table>
  <div style="margin-top:12px">{next_link}</div>
</body>
</html>
    """.strip()

    return HTMLResponse(html)
