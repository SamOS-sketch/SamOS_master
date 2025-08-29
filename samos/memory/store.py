from __future__ import annotations
import sqlite3
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Iterable, Optional

DEFAULT_DB = "samos.db"

SchemaSQL = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    tags TEXT NOT NULL,          -- JSON list
    importance INTEGER NOT NULL, -- 1..5
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_mem_text ON memories(text);
CREATE INDEX IF NOT EXISTS ix_mem_created ON memories(created_at);
"""

@dataclass
class MemoryItem:
    id: int
    text: str
    tags: List[str]
    importance: int
    created_at: str

class MemoryStore:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(SchemaSQL)

    def add_memory(self, text: str, tags: List[str] | None = None, importance: int = 3) -> int:
        if not text or not text.strip():
            raise ValueError("memory text is required")
        if importance < 1 or importance > 5:
            raise ValueError("importance must be 1..5")
        tags = tags or []
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO memories(text, tags, importance) VALUES (?, ?, ?)",
                (text.strip(), json.dumps(tags), importance),
            )
            return int(cur.lastrowid)

    def search(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """
        MVP search: simple LIKE match, ordering by:
        - more occurrences of query in text (approx via LENGTH diff)
        - higher importance
        - newer created_at
        """
        if not query or not query.strip():
            return []
        q = f"%{query.strip()}%"
        sql = """
        SELECT id, text, tags, importance, created_at,
               -- crude 'score': shorter replace -> more matches
               (LENGTH(text) - LENGTH(REPLACE(LOWER(text), LOWER(?), ''))) AS hits
        FROM memories
        WHERE text LIKE ?
        ORDER BY hits DESC, importance DESC, created_at DESC
        LIMIT ?
        """
        with self._conn() as c:
            rows = c.execute(sql, (query, q, top_k)).fetchall()
        out: List[MemoryItem] = []
        for r in rows:
            out.append(MemoryItem(
                id=r["id"],
                text=r["text"],
                tags=json.loads(r["tags"] or "[]"),
                importance=int(r["importance"]),
                created_at=str(r["created_at"]),
            ))
        return out
