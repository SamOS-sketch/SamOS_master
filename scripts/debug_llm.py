import os
import sys
import logging

# optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from samos.providers.llm_service import LLMService

def main():
    prompt = " ".join(sys.argv[1:]) or "Say hello"
    provider = "openai"
    print(f"[debug] provider={provider}")
    print(f"[debug] has_api_key={bool(os.getenv('OPENAI_API_KEY'))}")
    try:
        llm = LLMService(provider=provider)
        text, latency = llm.generate(prompt)
        print(f"[ok] latency_ms={latency}")
        print(text)
    except Exception as e:
        print("[fail]", type(e).__name__, str(e))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
