from samos.client import SamOSClient

c = SamOSClient("http://localhost:8000")
sid = c.start_session()["session_id"]
c.set_mode(sid, "sandbox")
c.put_memory(sid, "demo.persist", "stay", meta={"note": "persistence test"})
c.create_emm(sid, "Spark", "prep before restart")
print("SID:", sid)  # copy this after it runs
