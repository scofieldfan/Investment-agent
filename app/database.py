import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = "finance.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_cache (
            cache_key TEXT PRIMARY KEY,
            data TEXT,
            updated_at TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()


def get_cached_data(key: str, max_age_days: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT data, updated_at FROM api_cache WHERE cache_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()

    if row:
        updated_at = datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - updated_at < timedelta(days=max_age_days):
            return json.loads(row["data"])
    return None


def save_to_cache(key: str, data: dict):
    conn = get_db_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO api_cache (cache_key, data, updated_at)
        VALUES (?, ?, ?)
    """,
        (key, json.dumps(data), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()
