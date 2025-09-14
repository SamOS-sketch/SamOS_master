# tools/db_bootstrap.py
import argparse
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

BASELINE_REV = "2a99e8b569fa"  # A8 baseline
REV_HEX_RE = re.compile(r"^[0-9a-f]{12}$", re.IGNORECASE)

def run(cmd: str) -> int:
    print(">", cmd)
    return subprocess.call(cmd, shell=True)

def py_alembic(args: str) -> int:
    return run(f"python -m alembic -c alembic.ini {args}")

def resolve_sqlite_path(database_url: str) -> Path | None:
    if not database_url or not database_url.startswith("sqlite"):
        return None
    if database_url.startswith("sqlite:///"):
        raw = database_url.replace("sqlite:///", "", 1)
        return Path(raw).resolve()
    parsed = urlparse(database_url)
    if parsed.scheme == "sqlite" and parsed.path:
        return Path(parsed.path).resolve()
    return None

def read_current_version(db_file: Path) -> list[str]:
    if not db_file.exists():
        return []
    con = sqlite3.connect(str(db_file))
    try:
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is None:
            return []
        return [r[0] for r in cur.execute("SELECT version_num FROM alembic_version")]
    finally:
        con.close()

def is_valid_rev(v: str) -> bool:
    return bool(REV_HEX_RE.match(v))

def main():
    ap = argparse.ArgumentParser(description="SamOS DB bootstrap")
    ap.add_argument("--reset", action="store_true", help="Delete DB file (sqlite) and reapply migrations")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "sqlite:///./samos.db")
    db_file = resolve_sqlite_path(db_url)

    if args.reset and db_file and db_file.exists():
        print(f"[db] --reset: deleting {db_file}")
        db_file.unlink(missing_ok=True)
        print("[db] stamping baseline + upgrading head")
        rc = py_alembic(f"stamp {BASELINE_REV}")
        if rc: sys.exit(rc)
        sys.exit(py_alembic("upgrade head"))

    if db_file and not db_file.exists():
        print(f"[db] {db_file} not found → fresh upgrade")
        rc = py_alembic(f"stamp {BASELINE_REV}")
        if rc: sys.exit(rc)
        sys.exit(py_alembic("upgrade head"))

    versions = read_current_version(db_file) if db_file else []
    print(f"[db] DATABASE_URL={db_url}")
    print(f"[db] alembic_version rows: {versions or '[]'}")

    needs_fix = len(versions) != 1 or not is_valid_rev(versions[0])
    if needs_fix:
        print("[db] bad or missing alembic_version → stamping baseline + upgrading head")
        rc = py_alembic(f"stamp {BASELINE_REV}")
        if rc: sys.exit(rc)
        sys.exit(py_alembic("upgrade head"))

    print("[db] upgrading to head")
    sys.exit(py_alembic("upgrade head"))

if __name__ == "__main__":
    sys.exit(main())
