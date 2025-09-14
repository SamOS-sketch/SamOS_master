import os, sqlite3, subprocess, tempfile, shutil, sys

PY = sys.executable  # use the same interpreter pytest is using

def _run(cmd: str):
    subprocess.check_call(cmd, shell=True)

def _alembic(args: str):
    _run(f'"{PY}" -m alembic -c alembic.ini {args}')

def init_temp_db_env():
    tmpdir = tempfile.mkdtemp()
    db = os.path.join(tmpdir, "samos.db")
    os.environ["DB_PATH"] = db
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    _alembic("stamp base")
    _alembic("upgrade head")
    return tmpdir, db

def test_images_table_has_drift_score():
    tmp, db = init_temp_db_env()
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(images)")]
        assert "drift_score" in cols
    finally:
        try:
            con.close()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

def test_single_head_only():
    out = subprocess.check_output(f'"{PY}" -m alembic -c alembic.ini heads --verbose', shell=True).decode()
    assert out.count("Rev:") == 1
