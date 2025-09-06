from samos.skills.echo import EchoSkill
from samos.core.soulprint import Soulprint
from samos.skills.base import UserMessage, Context

def dump(label, s: str):
    print(f"\n--- {label} ---")
    print("repr:", repr(s))
    print("codes:", [ord(c) for c in s])

# ---- Router test reproduction (X | t | s: Hello) ----
sp_x = Soulprint({"identity": {"name": "X", "tone": "t"}})
ctx_x = Context(soulprint=sp_x)
out_x = EchoSkill().run(UserMessage(text="Hello"), ctx_x).text
dump("router_out", out_x)
print("contains 'Hello'?:", "Hello" in out_x)
print("contains 'X | t'?:", "X | t" in out_x)

# ---- Echo test reproduction (Sam  , warm: ping) ----
sp_sam = Soulprint({"identity": {"name": "Sam", "tone": "warm"}})
ctx_sam = Context(soulprint=sp_sam)
out_sam = EchoSkill().run(UserMessage(text="ping"), ctx_sam).text
dump("echo_out", out_sam)

expected = "Sam  , warm: ping"  # what the test asserts
dump("echo_expected", expected)
print("equal?:", out_sam == expected)
