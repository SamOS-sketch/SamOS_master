# scripts/migrate_phase8.py
import os
from sqlalchemy import create_engine, text

# DB path: adjust if yours is elsewhere
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "samos.db")
DB_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DB_URL, future=True)

statements = [
    "ALTER TABLE images ADD COLUMN provider TEXT;",
    "ALTER TABLE images ADD COLUMN tier TEXT;",
    "ALTER TABLE images ADD COLUMN latency_ms INTEGER;",
    "ALTER TABLE images ADD COLUMN reference_used BOOLEAN;",
    "ALTER TABLE images ADD COLUMN provenance TEXT;"
]

with engine.connect() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            print("OK  ->", stmt)
        except Exception as e:
            # If the column already exists, SQLite will error with 'duplicate column name'
            print("SKIP->", stmt, "::", e)
    conn.commit()

print("\nDone. If most lines say OK (or SKIP for existing), migration is fine.")
