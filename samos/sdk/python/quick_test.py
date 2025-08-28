from samos.client import SamOSClient

if __name__ == "__main__":
    c = SamOSClient(base_url="http://localhost:8000")
    session = c.start_session()
    sid = session["session_id"]
    print("Session:", session)

    print("Mode before:", c.get_mode(sid))
    print("Set mode to sandbox:", c.set_mode(sid, "sandbox"))

    c.put_memory(sid, "demo.note", "hello world", meta={"source": "poc"})
    print("Memory get:", c.get_memory(sid, "demo.note"))
    print("Image:", c.generate_image(sid, prompt="sunrise over calm sea"))
    print("EMMs:", c.list_emms(sid, limit=5))
