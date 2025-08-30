# samos/api/utils/db_retry.py
import time

from sqlalchemy.exc import OperationalError


def commit_with_retry(db, retries: int = 5, base_delay: float = 0.05):
    """
    Commits the current transaction with exponential backoff if SQLite is briefly locked.
    Retries up to `retries` times, waiting base_delay * (2**attempt) seconds between tries.
    Raises the last error if all retries fail.
    """
    attempt = 0
    while True:
        try:
            db.commit()
            return
        except OperationalError as e:
            msg = str(e).lower()
            if "database is locked" in msg or "timeout" in msg:
                if attempt >= retries:
                    raise
                time.sleep(base_delay * (2**attempt))
                attempt += 1
                continue
            # Not a transient lock/timeout -> bubble up
            raise
