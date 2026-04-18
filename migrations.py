import os
from pathlib import Path
from storage import get_connection

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    name TEXT,
    content TEXT NOT NULL,
    mode_id INTEGER NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notes_name ON notes(name);
CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at DESC);

CREATE TABLE IF NOT EXISTS modes (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    system_prompt TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keybinds (
    action TEXT PRIMARY KEY,
    key_combo TEXT NOT NULL
);
"""

def bootstrap_modes(conn):
    prompts_dir = Path("prompts")
    if not prompts_dir.exists():
        return
    for prompt_file in prompts_dir.glob("*.txt"):
        name = prompt_file.stem
        content = prompt_file.read_text(encoding="utf-8").strip()
        conn.execute(
            "INSERT OR IGNORE INTO modes (name, system_prompt) VALUES (?, ?)", 
            (name, content)
        )

def bootstrap_keybinds(conn):
    default_binds = [
        ("record_new_note", "f8"),
        ("record_append_latest", "f7"),
        ("toggle_autopaste", "ctrl+alt+v"),
        ("mode:slack", "ctrl+alt+1"),
        ("mode:email", "ctrl+alt+2"),
        ("mode:requirements", "ctrl+alt+3"),
        ("mode:none", "ctrl+alt+4"),
        ("mode:notes", "ctrl+alt+5"),
        ("mode:translate", "ctrl+alt+6"),
        ("mode:pl_requirements", "ctrl+alt+7"),
    ]
    for action, combo in default_binds:
        conn.execute(
            "INSERT OR IGNORE INTO keybinds (action, key_combo) VALUES (?, ?)",
            (action, combo)
        )

def bootstrap_settings(conn):
    settings = [
        ("autopaste_enabled", "false"),
        ("active_mode", "slack")
    ]
    for k, v in settings:
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (k, v)
        )

def run_migrations():
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA_V1)
        bootstrap_modes(conn)
        bootstrap_keybinds(conn)
        bootstrap_settings(conn)
        conn.commit()

if __name__ == "__main__":
    run_migrations()
    print("Database migrated and bootstrapped successfully.")
