# tools/db_peek.py
import os, sqlite3, json, sys
db_path = os.getenv("DB_PATH", "./samos.db")
print(f"[peek] DB_PATH={db_path}")
con = sqlite3.connect(db_path)
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("[peek] tables:", tables)
if "images" in tables:
    cols = [c[1] for c in cur.execute("PRAGMA table_info(images)")]
    print("[peek] images columns:", cols)
else:
    print("[peek] images table not found")
con.close()
