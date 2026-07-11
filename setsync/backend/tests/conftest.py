import pytest
import sqlite3
import os

@pytest.fixture(scope="module", autouse=True)
def cleanup_database():
    # SQLite DB file path
    db_path = "setsync.db"
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        # Fetch all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall() if row[0] != "alembic_version"]
        
        # Clear tables
        for table in tables:
            cursor.execute(f"DELETE FROM {table};")
            
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
    finally:
        conn.close()
