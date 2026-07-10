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
    try:
        cursor.execute("ALTER TABLE file_cache ADD COLUMN image_hash TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_cached_file(path: str) -> Optional[Tuple[int, float, str, Optional[str]]]:
    """Returns (size, mtime, hash, image_hash) if path exists, otherwise None."""
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT size, mtime, hash, image_hash FROM file_cache WHERE path = ?", (path,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2], row[3]
    return None

def update_cached_file(path: str, size: int, mtime: float, file_hash: str, image_hash: Optional[str], scanned_at: datetime.datetime):
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO file_cache (path, size, mtime, hash, image_hash, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (path, size, mtime, file_hash, image_hash, scanned_at.isoformat()))
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
    cursor.execute("DELETE FROM file_cache WHERE datetime(scanned_at) < datetime(?)", (scan_start.isoformat(),))
    conn.commit()
    conn.close()

def get_config(key: str) -> Optional[str]:
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def set_config(key: str, value: str):
    conn = sqlite3.connect(AGENT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
