import os
import time
import json
import logging
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)


class OpenAIConfig:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = int(os.getenv("OPENAI_REQUEST_TIMEOUT_SECS", "30"))
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "800"))
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        self.log_latency = os.getenv("LOG_PROVIDER_LATENCY", "false").lower() == "true"

        # Project + Org (needed for sk-proj keys in many orgs)
        self.project_id = os.getenv("OPENAI_PROJECT_ID")  # e.g., proj_xxx
        self.org_id = os.getenv("OPENAI_ORG_ID")          # e.g., org_xxx

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY missing")

    @property
    def responses_url(self) -> str:
        # Newer unified endpoint
        return f"{self.base}/responses"


class OpenAIClient:
    """OpenAI Responses client with safe timeouts and retries."""

    def __init__(self, cfg: OpenAIConfig):
        self.cfg = cfg
        self._session = requests.Session()
        self._headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }
        if self.cfg.project_id:
            self._headers["OpenAI-Project"] = self.cfg.project_id
        if self.cfg.org_id:
            self._headers["OpenAI-Organization"] = self.cfg.org_id

    def _should_retry(self, status: Optional[int]) -> bool:
        if status is None:
            return True
        if status == 429:
            return True
        if 500 <= status < 600:
            return True
        return False

    def _serialize_messages_to_input(self, messages: List[Dict[str, Any]]) -> str:
        """Flatten chat-style messages to a single prompt string for /responses."""
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n".join(parts).strip()

    def _extract_text(self, data: Dict[str, Any]) -> str:
        """
        Try multiple shapes:
        - data['output_text'] (common)
        - data['output'][i]['content'][j]['text'] (raw)
        - fallback to chat-style choices[0].message.content if present
        """
        if isinstance(data, dict):
            ot = data.get("output_text")
            if isinstance(ot, str) and ot.strip():
                return ot.strip()
            output = data.get("output")
            if isinstance(output, list):
                segs = []
                for item in output:
                    content = item.get("content")
                    if isinstance(content, list):
                        for c in content:
                            t = c.get("text") or c.get("content")
                            if isinstance(t, str):
                                segs.append(t)
                if segs:
                    return "".join(segs).strip()
            # legacy chat shape if gateway translated it
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                msg = choices[0].get("message") or {}
                txt = msg.get("content")
                if isinstance(txt, str):
                    return txt.strip()
        raise ValueError("no text found in response payload")

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        body = {
            "model": self.cfg.model,
            "input": self._serialize_messages_to_input(messages),
            "max_output_tokens": self.cfg.max_tokens,  # Responses API name
            "temperature": self.cfg.temperature,
        }

        attempts = 0
        start = time.time()

        while True:
            attempts += 1
            try:
                r = self._session.post(
                    self.cfg.responses_url,
                    headers=self._headers,
                    json=body,
                    timeout=self.cfg.timeout,
                )
                status = r.status_code
                if status >= 400:
                    if self._should_retry(status) and attempts < 3:
                        time.sleep(0.5 * (2 ** (attempts - 1)))
                        continue
                    r.raise_for_status()

                data = r.json()
                text = self._extract_text(data)
                latency_ms = int((time.time() - start) * 1000)

                if self.cfg.log_latency:
                    log.info(
                        "provider=openai event=llm.ok latency_ms=%s model=%s",
                        latency_ms,
                        self.cfg.model,
                    )

                return {"ok": True, "text": text, "latency_ms": latency_ms}

            except requests.exceptions.RequestException as e:
                if attempts < 3:
                    time.sleep(0.5 * (2 ** (attempts - 1)))
                    continue
                latency_ms = int((time.time() - start) * 1000)
                if self.cfg.log_latency:
                    log.warning(
                        "provider=openai event=llm.fail latency_ms=%s error=%s",
                        latency_ms,
                        str(e),
                    )
                return {"ok": False, "error": str(e)}
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                latency_ms = int((time.time() - start) * 1000)
                if self.cfg.log_latency:
                    log.warning(
                        "provider=openai event=llm.fail latency_ms=%s error=parse_error",
                        latency_ms,
                    )
                return {"ok": False, "error": f"response.parse_error: {e}"}
