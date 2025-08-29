from pathlib import Path
from samos.memory.store import MemoryStore

def test_add_and_search_returns_results(tmp_path: Path):
    db = tmp_path / "test.db"
    ms = MemoryStore(str(db))
    # Add some memories
    ms.add_memory("We shipped Phase 8 Observability today", tags=["work","phase8"], importance=4)
    ms.add_memory("Remember to keep tone warm and candid", tags=["voice"], importance=5)
    ms.add_memory("Buy coffee beans", tags=["personal"], importance=2)

    r = ms.search("tone")
    assert len(r) >= 1
    assert "tone" in r[0].text.lower()

def test_importance_bounds(tmp_path: Path):
    db = tmp_path / "x.db"
    ms = MemoryStore(str(db))
    try:
        ms.add_memory("ok", importance=0)
        assert False, "should have raised"
    except ValueError:
        pass
    try:
        ms.add_memory("ok", importance=6)
        assert False, "should have raised"
    except ValueError:
        pass

def test_empty_query_returns_empty(tmp_path: Path):
    db = tmp_path / "y.db"
    ms = MemoryStore(str(db))
    ms.add_memory("SamOS loves clean tests", importance=3)
    assert ms.search("") == []
