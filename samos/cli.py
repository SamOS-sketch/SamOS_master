import argparse
import logging

from samos.runtime import llm_generate
from samos.runtime.models import UserMessage, Context, Response
from samos.skills.hello_skill import HelloSkill
from samos.runtime.router import Router

# Try to load your real Soulprint if available; fall back to a tiny stub.
def _load_soulprint():
    try:
        # adjust if your loader is elsewhere
        from samos.core.soulprint import load_soulprint
        return load_soulprint()
    except Exception:
        class _Stub:
            def voice_tag(self): return "Sam"
            def system_prompt(self): return "You are warm, candid, playful. Be concise."
        return _Stub()

def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=str, nargs="+")
    parser.add_argument("--provider", default=None, help="openai | echo")
    args = parser.parse_args()

    text_in = " ".join(args.prompt)

    # Build router with our HelloSkill (LLM-backed)
    soulprint = _load_soulprint()
    ctx = Context(soulprint=soulprint)
    router = Router(skills=[HelloSkill()])

    msg = UserMessage(text=text_in)
    resp: Response = router.handle(msg, ctx)

    print(resp.text)

if __name__ == "__main__":
    main()
