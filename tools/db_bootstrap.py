# tools/db_bootstrap.py
"""
SamOS DB bootstrap (V1)
- If Alembic is available + configured -> stamp baseline (optional) and upgrade head
- Otherwise -> create tables via SQLAlchemy Base.metadata.create_all()
- Supports --reset to delete sqlite DB and start clean
- Never hard-fails just because alembic isn't present; fresh clones must work.

Usage:
  python tools/db_bootstrap.py
  python tools/db_bootstrap.py --reset
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Import your declarative Base and models (Image, Event, Session, etc.)
from samos.api.db import Base

# Optional: baseline revision used by your migration history (safe if missing)
BASELINE_REV = "2a99e8b569fa"  # adjust if your repo differs
REV_HEX_RE = re.compile(r"^[0-9a-f]{12}$", re.IGNORECASE)


# ---------- helpers ----------
def _print(msg: str) -> None:
    print(f"[db] {msg}")


def run(cmd: list[str] | str) -> int:
    # Use list form when possible; keep shell for Py <3.8 on Windows compatibility
    if isinstance(cmd, list):
        _print("> " + " ".join(cmd))
        try:
            return subprocess.call(cmd)
        except FileNotFoundError:
            return 127
    else:
        _print("> " + cmd)
        return subprocess.call(cmd, shell=True)


def have_alembic() -> bool:
    """Detect if alembic is importable and alembic.ini exists."""
    if not Path("alembic.ini").exists():
        return False
    try:
        __import__("alembic")
        return True
    except Exception:
        return False


def sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url or not database_url.startswith("sqlite"):
        return None
    if database_url.startswith("sqlite:///"):
        raw = database_url.replace("sqlite:///", "", 1)
        return Path(raw).resolve()
    parsed = urlparse(database_url)
    if parsed.scheme == "sqlite" and parsed.path:
        return Path(parsed.path).resolve()
    return None


def read_alembic_versions(db_file: Path) -> list[str]:
    if not db_file or not db_file.exists():
        return []
    con = sqlite3.connect(str(db_file))
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        )
        if cur.fetchone() is None:
            return []
        return [r[0] for r in cur.execute("SELECT version_num FROM alembic_version")]
    finally:
        con.close()


def safe_create_all(database_url: str) -> None:
    """Create tables directly via SQLAlchemy for bootstrap/fallback."""
    _print(f"create_all() on {database_url}")
    engine = create_engine(database_url, future=True)
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as e:
        _print(f"create_all failed: {e}")
        raise


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser(description="SamOS DB bootstrap")
    ap.add_argument("--reset", action="store_true", help="Delete sqlite DB and rebuild")
    ap.add_argument(
        "--no-alembic",
        action="store_true",
        help="Skip Alembic even if present; use create_all()",
    )
    ap.add_argument(
        "--alembic-only",
        action="store_true",
        help="Require Alembic; fail if not available",
    )
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "sqlite:///samos.db")
    db_file = sqlite_path_from_url(db_url)

    _print(f"DATABASE_URL={db_url}")

    # Handle --reset for sqlite
    if args.reset and db_file and db_file.exists():
        _print(f"--reset: deleting {db_file}")
        try:
            db_file.unlink(missing_ok=True)
        except Exception as e:
            _print(f"warning: failed to delete DB file: {e}")

    use_alembic = have_alembic() and not args.no_alembic

    if args.alembic_only and not use_alembic:
        _print("alembic-only requested but Alembic not available/alembic.ini missing")
        return 2

    if use_alembic:
        # Optionally stamp baseline when DB is fresh or alembic_version is broken
        need_stamp = False
        if db_file and db_file.exists():
            versions = read_alembic_versions(db_file)
            _print(f"alembic_version rows: {versions or '[]'}")
            if len(versions) != 1 or not REV_HEX_RE.match(versions[0] or ""):
                need_stamp = True
        else:
            need_stamp = True

        if need_stamp and BASELINE_REV:
            rc = run(["python", "-m", "alembic", "-c", "alembic.ini", "stamp", BASELINE_REV])
            if rc:
                _print(f"alembic stamp failed (rc={rc}); falling back to create_all()")
                safe_create_all(db_url)
                return 0

        rc = run(["python", "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"])
        if rc:
            _print(f"alembic upgrade failed (rc={rc}); falling back to create_all()")
            safe_create_all(db_url)
            return 0

        _print("alembic upgrade head OK")
        return 0

    # No Alembic → create tables directly
    _print("Alembic not available or disabled -> using create_all()")
    safe_create_all(db_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
