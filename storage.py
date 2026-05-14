import sqlite3
import os
from pathlib import Path

DB_FILE = "keynote.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def _row_to_dict(row):
    """Convert sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)

def _rows_to_dicts(rows):
    """Convert list of sqlite3.Row to list of dicts."""
    return [dict(r) for r in rows]

def execute_query(query, params=()):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

def fetch_all(query, params=()):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return _rows_to_dicts(cursor.fetchall())

def fetch_one(query, params=()):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return _row_to_dict(cursor.fetchone())
