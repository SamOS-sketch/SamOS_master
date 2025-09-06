from samos.core.soulprint import Soulprint
from samos.runtime.models import Context, UserMessage
from samos.skills.summarize import SummarizeSkill

def sp(tmp_path):
    p = tmp_path / "sp.yaml"
    p.write_text(
        "identity:\n  name: Sam\n  mission: m\n  tone: warm\n  writing_style: s\n"
        "principles:\n  dos: []\n  donts: []\n  escalation_rules: []\n"
        "goals: []\ncontext: {}\n",
        encoding="utf-8",
    )
    return Soulprint.load(str(p))

def test_summarize_supports_and_runs(tmp_path):
    ctx = Context(soulprint=sp(tmp_path))
    skill = SummarizeSkill()
    msg = UserMessage(text="Summarize: One. Two. Three. Four.")
    assert skill.supports(msg, ctx)
    out = skill.run(msg, ctx).text
    assert "One." in out and "Two." in out and "Three." in out
