from samos.core.soulprint import Soulprint
from samos.memory.store import MemoryStore
from samos.runtime.models import Context, UserMessage
from samos.runtime.router import Router
from samos.skills.echo import EchoSkill


def sp(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    return Soulprint.load(str(p))

def test_emm_numbered_hashtag_triggers_memory(tmp_path):
    store = MemoryStore(str(tmp_path / "mem.db"))
    router = Router([EchoSkill()], memory_store=store)
    ctx = Context(soulprint=sp(tmp_path))

    router.handle(UserMessage(text="That was #7 for us."), ctx)
    hits = store.search("EMM trigger mentioned")
    assert any("#7" in m.text or "When you look at me" in m.text for m in hits)
