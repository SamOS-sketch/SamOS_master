
# samos/providers/comfyui_images.py
from __future__ import annotations

import io
import os
import uuid
import time
from typing import Dict, Any, Optional, Tuple

import requests
from PIL import Image

from .image_base import ImageProvider, prompt_hash, registry


def _outputs_dir() -> str:
    d = os.path.abspath(os.getenv("OUTPUTS_DIR", "outputs"))
    os.makedirs(d, exist_ok=True)
    return d


def _persist_png(image_bytes: bytes) -> Tuple[str, str]:
    """
    Save bytes as PNG under OUTPUTS_DIR. Returns (local_path, file_url).
    """
    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    file_id = uuid.uuid4().hex
    local_path = os.path.join(_outputs_dir(), f"{file_id}.png")
    img.save(local_path, format="PNG")
    return local_path, f"file://{local_path}"


def _comfy_cfg() -> Dict[str, Any]:
    return {
        "url": os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
        "timeout": int(os.getenv("COMFYUI_TIMEOUT", "60")),
    }


@registry.register
class ComfyUIProvider(ImageProvider):
    """
    ComfyUI provider with mode switch:
      - COMFYUI_MODE=stub  -> return a stub image and persist tiny PNG (default)
      - COMFYUI_MODE=fail  -> raise an error to force fallback
      - COMFYUI_MODE=live  -> call ComfyUI HTTP API and persist result locally

    Expected live API (flexible):
      POST {COMFYUI_URL}/prompt
        JSON: { "prompt": str, "seed"?: int, "reference_url"?: str, "size"?: str }
      Response EITHER:
        a) JSON: { "ok": true, "image_url": "http://.../image.png" }
        b) Raw image bytes (PNG/JPEG)
    """

    name = "comfyui"

    def generate(
        self,
        session_id: Optional[str],
        prompt: str,
        size: str,
        reference_image: Optional[str],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        mode = (os.getenv("COMFYUI_MODE") or "stub").lower().strip()
        started = time.perf_counter()

        # --- Forced failure (prove fallback chain) ---
        if mode == "fail":
            raise RuntimeError("ComfyUI forced failure (COMFYUI_MODE=fail)")

        # --- Live HTTP path ---
        if mode in ("live", "http"):
            cfg = _comfy_cfg()
            try:
                image_bytes, remote_url = self._call_comfy_http(
                    base_url=cfg["url"],
                    timeout=cfg["timeout"],
                    prompt=prompt,
                    reference_url=reference_image,
                    size=size,
                    seed=kwargs.get("seed"),
                )
                local_path, file_url = _persist_png(image_bytes)
                latency_ms = int((time.perf_counter() - started) * 1000)
                image_id = os.path.splitext(os.path.basename(local_path))[0]

                return {
                    "url": file_url,
                    "local_path": local_path,
                    "provider": self.name,
                    "image_id": image_id,
                    "reference_used": bool(reference_image),
                    "status": "ok",
                    "meta": {
                        "latency_ms": latency_ms,
                        "prompt_hash": prompt_hash(prompt),
                        "size": size,
                        "session_id": session_id,
                        "mode": mode,
                        "remote_url": remote_url,
                        "engine": "comfyui",
                    },
                }
            except Exception as e:
                # Bubble up as failure so router can fall back
                raise RuntimeError(f"ComfyUI live error: {e}") from e

        # --- Default: stub success (no external dependency) ---
        # Persist a tiny PNG so drift scoring has a local_path.
        tiny = Image.new("RGB", (1, 1))
        buf = io.BytesIO()
        tiny.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        local_path, file_url = _persist_png(img_bytes)
        image_id = os.path.splitext(os.path.basename(local_path))[0]
        latency_ms = int((time.perf_counter() - started) * 1000)

        return {
            "url": file_url,
            "local_path": local_path,
            "provider": self.name,
            "image_id": image_id,
            "reference_used": bool(reference_image),
            "status": "ok",
            "meta": {
                "latency_ms": latency_ms,
                "prompt_hash": prompt_hash(prompt),
                "size": size,
                "session_id": session_id,
                "mode": mode,  # "stub"
                "engine": "comfyui",
            },
        }

    # ---- helpers ----

    def _call_comfy_http(
        self,
        base_url: str,
        timeout: int,
        prompt: str,
        reference_url: Optional[str],
        size: str,
        seed: Optional[int],
    ) -> Tuple[bytes, Optional[str]]:
        """
        Call ComfyUI endpoint and return image bytes and optional remote URL.
        Handles two common patterns:
          1) JSON with {"ok": true, "image_url": "..."} -> we download the image
          2) Direct image bytes
        """
        payload: Dict[str, Any] = {"prompt": prompt}
        if seed is not None:
            payload["seed"] = seed
        if reference_url:
            payload["reference_url"] = reference_url
        if size:
            payload["size"] = size  # harmless passthrough if the workflow ignores it

        resp = requests.post(f"{base_url}/prompt", json=payload, timeout=timeout)
        resp.raise_for_status()

        ctype = (resp.headers.get("content-type") or "").lower()
        if "application/json" in ctype:
            data = resp.json()
            if not data or not data.get("ok"):
                raise RuntimeError(f"ComfyUI returned error JSON: {data}")
            img_url = data.get("image_url")
            if not img_url:
                raise RuntimeError("ComfyUI returned ok=true but no image_url")
            img = requests.get(img_url, timeout=timeout)
            img.raise_for_status()
            return img.content, img_url

        # otherwise treat response body as image bytes
        return resp.content, None
