import sqlite3
import datetime
from typing import Optional, Tuple
from agent.config import AGENT_DB_PATH

def init_agent_db():
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            path TEXT PRIMARY KEY,
            size INTEGER,
            mtime REAL,
            hash TEXT,
            scanned_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_cached_file(path: str) -> Optional[Tuple[int, float, str]]:
    """Returns (size, mtime, hash) if path exists, otherwise None."""
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT size, mtime, hash FROM file_cache WHERE path = ?", (path,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None

def update_cached_file(path: str, size: int, mtime: float, file_hash: str, scanned_at: datetime.datetime):
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO file_cache (path, size, mtime, hash, scanned_at)
        VALUES (?, ?, ?, ?, ?)
    """, (path, size, mtime, file_hash, scanned_at.isoformat()))
    conn.commit()
    conn.close()

def update_scanned_time(path: str, scanned_at: datetime.datetime):
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE file_cache SET scanned_at = ? WHERE path = ?", (scanned_at.isoformat(), path))
    conn.commit()
    conn.close()

def delete_stale_cache(scan_start: datetime.datetime):
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    # Delete entries that were not updated in this scan run
    cursor.execute("DELETE FROM file_cache WHERE datetime(scanned_at) < datetime(?)", (scan_start.isoformat(),))
    conn.commit()
    conn.close()
