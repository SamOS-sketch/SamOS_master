from samos.client import SamOSClient

sid = "f5b40c94-f13c-41f3-9a53-2cfd519604ac"   # <-- your SID here

c = SamOSClient("http://localhost:8000")
print("Mode after restart:", c.get_mode(sid))
print("Memory after restart:", c.get_memory(sid, "demo.persist"))
print("Recent EMMs:", c.list_emms(sid, 5))
