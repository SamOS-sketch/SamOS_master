from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.runtime.router import Router
from samos.skills.echo import EchoSkill


def test_router_uses_echo_skill(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: X\n  mission: m\n  tone: t\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    sp = Soulprint.load(str(p))
    ctx = Context(soulprint=sp)
    router = Router([EchoSkill()])
    resp = router.handle(UserMessage(text="Hello"), ctx)
    assert "Hello" in resp.text and "X · t" in resp.text
