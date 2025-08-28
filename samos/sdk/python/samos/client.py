import httpx


class SamOSClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(timeout=30)

    # Sessions
    def start_session(self):
        r = self.http.post(f"{self.base_url}/session/start")
        r.raise_for_status()
        return r.json()

    def get_mode(self, session_id: str):
        r = self.http.get(
            f"{self.base_url}/session/mode", params={"session_id": session_id}
        )
        r.raise_for_status()
        return r.json()

    def set_mode(self, session_id: str, mode: str):
        r = self.http.post(
            f"{self.base_url}/session/mode",
            json={"session_id": session_id, "mode": mode},
        )
        r.raise_for_status()
        return r.json()

    # Memory
    def put_memory(self, session_id: str, key: str, value: str, meta: dict = None):
        r = self.http.post(
            f"{self.base_url}/memory",
            json={
                "session_id": session_id,
                "key": key,
                "value": value,
                "meta": meta or {},
            },
        )
        r.raise_for_status()
        return r.json()

    def get_memory(self, session_id: str, key: str):
        r = self.http.get(
            f"{self.base_url}/memory", params={"session_id": session_id, "key": key}
        )
        r.raise_for_status()
        return r.json()

    def list_memory(self, session_id: str):
        r = self.http.get(
            f"{self.base_url}/memory/list", params={"session_id": session_id}
        )
        r.raise_for_status()
        return r.json()

    # EMM
    def create_emm(
        self, session_id: str, type: str, message: str = None, meta: dict = None
    ):
        r = self.http.post(
            f"{self.base_url}/emm",
            json={
                "session_id": session_id,
                "type": type,
                "message": message,
                "meta": meta or {},
            },
        )
        r.raise_for_status()
        return r.json()

    def list_emms(self, session_id: str, limit: int = 50):
        r = self.http.get(
            f"{self.base_url}/emm/list",
            params={"session_id": session_id, "limit": limit},
        )
        r.raise_for_status()
        return r.json()

    def export_emms(self, session_id: str):
        r = self.http.get(
            f"{self.base_url}/emm/export", params={"session_id": session_id}
        )
        r.raise_for_status()
        return r.json()

    # Image
    def generate_image(self, session_id: str, prompt: str):
        r = self.http.post(
            f"{self.base_url}/image/generate",
            json={"session_id": session_id, "prompt": prompt},
        )
        if r.status_code >= 400:
            # raise with detail
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise RuntimeError(f"Image generation failed: {detail}")
        return r.json()
