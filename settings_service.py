from storage import execute_query, fetch_one, fetch_all

def get_setting(key: str) -> str | None:
    row = fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else None

def set_setting(key: str, value: str):
    execute_query("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def clear_setting(key: str):
    execute_query("DELETE FROM settings WHERE key = ?", (key,))

def is_autopaste_enabled() -> bool:
    return get_setting("autopaste_enabled") == "true"

def set_autopaste_enabled(enabled: bool):
    set_setting("autopaste_enabled", "true" if enabled else "false")
    
def get_active_mode() -> str:
    mode = get_setting("active_mode")
    return mode if mode else "slack"

def set_active_mode(mode: str):
    set_setting("active_mode", mode)

def get_active_note_id() -> int | None:
    val = get_setting("active_note_id")
    return int(val) if val else None

def set_active_note_id(note_id: int | None):
    if note_id is None:
        execute_query("DELETE FROM settings WHERE key = 'active_note_id'")
    else:
        set_setting("active_note_id", str(note_id))
