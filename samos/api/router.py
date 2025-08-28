import os, time
from typing import Dict, Any

# Try to use your existing event helpers if present; otherwise fallback to print.
try:
    # If you have samos.api.obs.events.py, adjust this import to match.
    from samos.api.obs.events import emit_event, log_emm  # type: ignore
except Exception:  # fallback no-op printers so this file works today
    def emit_event(name: str, payload: Dict[str, Any]):
        print(f"[event] {name} {payload}")
    def log_emm(code: str, context: Dict[str, Any]):
        emit_event("emm.log", {"code": code, **context})

# Provider registry
from samos.api.providers import (
    OpenAILLM, ClaudeLLM,
    OpenAIImages, StabilityImages, ComfyUIImages, LocalDiffusionImages, StubProvider
)

PROVIDER_REGISTRY_LLMS = {
    "openai": OpenAILLM,
    "claude": ClaudeLLM,
}

PROVIDER_REGISTRY_IMAGES = {
    "openai": OpenAIImages,
    "stability_api": StabilityImages,
    "comfyui": ComfyUIImages,
    "local_diffusion": LocalDiffusionImages,
    "stub": StubProvider,
}

def _split_chain(val: str) -> list[str]:
    return [p.strip() for p in (val or "").split(":") if p.strip()]

def _mode_default(mode: str, kind: str) -> str:
    if kind == "llm":
        return os.getenv("ROUTING_LLM_WORK" if mode == "work" else "ROUTING_LLM_SANDBOX", "openai")
    return os.getenv("ROUTING_IMG_WORK" if mode == "work" else "ROUTING_IMG_SANDBOX", "openai")

def _fallback_chain(kind: str) -> list[str]:
    key = "ROUTING_LLM_FALLBACK" if kind == "llm" else "ROUTING_IMG_FALLBACK"
    return _split_chain(os.getenv(key, ""))

class SamRouter:
    """
    Mode-aware router for LLM and Image providers with tiered prompts and failover.
    """
    def __init__(self, mode: str = "sandbox"):
        if mode not in ("work", "sandbox"):
            raise ValueError("mode must be 'work' or 'sandbox'")
        self.mode = mode
        self.reload()

    # ----- Route setup -----
    def reload(self):
        self.primary_llm = _mode_default(self.mode, "llm")
        self.primary_img = _mode_default(self.mode, "img")
        emit_event("llm.route.set", {"provider": self.primary_llm, "mode": self.mode})
        emit_event("image.route.set", {"provider": self.primary_img, "mode": self.mode})

    # ----- LLM routing -----
      # ----- LLM routing -----
    def llm_generate(self, prompt: str, **kw) -> Dict[str, Any]:
        """
        Policy:
          - WORK    mode: LLM -> openai only (no fallback)
          - SANDBOX mode: primary + configured fallbacks
        """
        if self.mode == "work":
            chain = [self.primary_llm]
            emit_event("llm.route.policy", {"mode": self.mode, "nofallback": True})
        else:
            chain = [self.primary_llm] + [p for p in _fallback_chain("llm") if p != self.primary_llm]
            emit_event("llm.route.policy", {"mode": self.mode, "nofallback": False, "chain": chain})

        last_err = None
        for prov in chain:
            start = time.perf_counter()
            try:
                out = PROVIDER_REGISTRY_LLMS[prov]().generate(prompt, **kw)
                emit_event("llm.ok", {"provider": prov, "latency": time.perf_counter() - start})
                return out
            except Exception as e:
                emit_event("llm.fail", {"provider": prov, "latency": time.perf_counter() - start, "error": str(e)})
                last_err = e

        if self.mode == "sandbox":
            log_emm("EMM_09", {"kind": "llm"})
        raise last_err or RuntimeError("LLM failed across chain")

    # ----- Image routing (tiers + failover) -----
        # ----- Image routing (tiers + failover) -----
    def image_generate(self, prompt_tiers: Dict[str, str], reference_image: str | None = None, **kw) -> Dict[str, Any]:
        """
        prompt_tiers expects keys from: {'primary','recovery','fallback'}
        Router tries all tiers for one provider before moving to the next.
        Policy: In WORK mode, Images -> openai with NO fallback.
        """
        # Build the provider chain according to policy
        if self.mode == "work":
            # No fallback in work mode by policy
            chain = [self.primary_img]
            emit_event("image.route.policy", {"mode": self.mode, "nofallback": True})
        else:
            # sandbox: primary + configured fallbacks (deduped)
            chain = [self.primary_img] + [p for p in _fallback_chain("img") if p != self.primary_img]
            emit_event("image.route.policy", {"mode": self.mode, "nofallback": False, "chain": chain})

        last_err = None
        for prov in chain:
            for tier in ("primary", "recovery", "fallback"):
                prompt = prompt_tiers.get(tier)
                if not prompt:
                    continue
                start = time.perf_counter()
                try:
                    out = PROVIDER_REGISTRY_IMAGES[prov]().generate(prompt, reference_image, tier, **kw)
                    emit_event("image.generate.ok", {
                        "provider": prov,
                        "tier": tier,
                        "latency": time.perf_counter() - start,
                        "reference_used": bool(reference_image)
                    })
                    return out
                except Exception as e:
                    emit_event("image.generate.fail", {
                        "provider": prov,
                        "tier": tier,
                        "latency": time.perf_counter() - start,
                        "error": str(e),
                        "reference_used": bool(reference_image)
                    })
                    last_err = e

        # Total failure across all tiers/providers
        log_emm("OneBounce", {"reason": "all_providers_failed", "mode": self.mode})
        raise last_err or RuntimeError("Image generation failed across all providers/tiers.")

