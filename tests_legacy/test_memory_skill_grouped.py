from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.skills.memory_recall import MemoryRecallSkill
from samos.memory.store import MemoryStore

def sp(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    return Soulprint.load(str(p))

def test_grouped_all(tmp_path):
    db = tmp_path / "db.sqlite"
    ms = MemoryStore(str(db))
    ms.add_memory("We have talked about tone before. Current message: X", tags=["theme","tone"], importance=3)
    ms.add_memory("Insight: Keep it concise", tags=["insight"], importance=4)
    ms.add_memory("EMM trigger mentioned: #7 moment", tags=["emm","relationship"], importance=5)
    ms.add_memory("Event: Phase 10 runtime shipped", tags=["event","milestone"], importance=4)

    skill = MemoryRecallSkill(store=ms)
    ctx = Context(soulprint=sp(tmp_path))
    out = skill.run(UserMessage(text="Memory: all"), ctx)
    t = out.text.lower()
    assert "themes:" in t and "insights:" in t and "emms:" in t and "events:" in t

def test_grouped_query(tmp_path):
    db = tmp_path / "db2.sqlite"
    ms = MemoryStore(str(db))
    ms.add_memory("We have talked about identity before. Current message: ...", tags=["theme","identity"], importance=3)
    ms.add_memory("Something else unrelated", tags=["other"], importance=1)

    skill = MemoryRecallSkill(store=ms)
    ctx = Context(soulprint=sp(tmp_path))
    out = skill.run(UserMessage(text="Memory: identity"), ctx)
    assert "themes:" in out.text.lower()
