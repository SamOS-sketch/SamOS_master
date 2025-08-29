from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.skills.memory_recall import MemoryRecallSkill
from samos.memory.store import MemoryStore

def test_memory_recall_returns_results(tmp_path):
    dbfile = tmp_path / "test.db"
    ms = MemoryStore(str(dbfile))
    ms.add_memory("SamOS remembers tone warm", tags=["voice"], importance=5)

    sp_yaml = tmp_path / "sp.yaml"
    sp_yaml.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n"
    )
    sp = Soulprint.load(str(sp_yaml))
    ctx = Context(soulprint=sp)
    skill = MemoryRecallSkill()
    msg = UserMessage(text="Memory: tone")
    out = skill.run(msg, ctx)
    assert "tone" in out.text.lower()
