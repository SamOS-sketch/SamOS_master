from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.skills.echo import EchoSkill


def test_echo_skill(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    sp = Soulprint.load(str(p))
    ctx = Context(soulprint=sp)
    skill = EchoSkill()
    assert skill.supports(UserMessage(text="ping"), ctx)
    out = skill.run(UserMessage(text="ping"), ctx)
    assert out.text == "Sam · warm: ping"
