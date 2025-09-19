import os, sqlite3
db = os.getenv("DB_PATH", "./samos.db")
con = sqlite3.connect(db)
print("DB:", db)
print("images (latest 3):")
for row in con.execute("""
    SELECT id, session_id, url, ref_used, drift_score,
           provider, status, latency_ms, created_at
    FROM images
    ORDER BY rowid DESC
    LIMIT 3
"""):
    print(row)
con.close()
