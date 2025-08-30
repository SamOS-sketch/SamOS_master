from samos.core.soulprint import Soulprint
from samos.memory.store import MemoryStore
from samos.runtime.models import Context, UserMessage
from samos.runtime.router import Router
from samos.skills.echo import EchoSkill


class _EchoThatRemembers(EchoSkill):
    # same echo, but asks router to remember the echoed text
    def run(self, msg, ctx):
        resp = super().run(msg, ctx)
        resp.meta["remember"] = {"text": msg.text, "tags": ["skill"], "importance": 3}
        return resp

def minimal_sp(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    return Soulprint.load(str(p))

def test_user_note_is_stored(tmp_path):
    sp = minimal_sp(tmp_path)
    db = tmp_path / "mem.db"
    store = MemoryStore(str(db))
    router = Router([EchoSkill()], memory_store=store)
    ctx = Context(soulprint=sp)

    router.handle(UserMessage(text="Remember: keep tone warm"), ctx)
    hits = store.search("tone")
    assert any("keep tone warm" in m.text for m in hits)

def test_skill_requested_memory_is_stored(tmp_path):
    sp = minimal_sp(tmp_path)
    db = tmp_path / "mem2.db"
    store = MemoryStore(str(db))
    router = Router([_EchoThatRemembers()], memory_store=store)
    ctx = Context(soulprint=sp)

    router.handle(UserMessage(text="store this line"), ctx)
    hits = store.search("store this line")
    assert hits and "store this line" in hits[0].text
