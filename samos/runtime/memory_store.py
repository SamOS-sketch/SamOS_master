# samos/runtime/memory_store.py
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


class MemoryStore:
    """
    Very small, file-backed memory store for notes/insights.
    Persists across runs by appending JSON lines to a file.
    """

    def __init__(self, path: str = ".samos/memory.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        # Touch file if missing
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    def add_note(self, text: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": "note",
            "text": text.strip(),
            "meta": meta or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def last(self, n: int = 3) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    items.append(json.loads(line))
        except FileNotFoundError:
            return []
        # Only notes for now; reverse chronological
        notes = [x for x in items if x.get("type") == "note"]
        return list(reversed(notes))[:n]
