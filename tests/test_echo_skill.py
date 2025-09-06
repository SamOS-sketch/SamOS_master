from samos.skills.echo import EchoSkill
from samos.core.soulprint import Soulprint
from samos.skills.base import UserMessage, Context

def test_echo_sam_format():
    sp = Soulprint({"identity": {"name": "Sam", "tone": "warm"}})
    out = EchoSkill().run(UserMessage(text="ping"), Context(soulprint=sp))
    assert out.text == "Sam  , warm: ping"

def test_echo_router_format_contains_pipe():
    sp = Soulprint({"identity": {"name": "X", "tone": "t"}})
    out = EchoSkill().run(UserMessage(text="Hello"), Context(soulprint=sp))
    assert "Hello" in out.text and "X | t" in out.text