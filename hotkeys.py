from storage import execute_query, fetch_all

def get_keybinds():
    rows = fetch_all("SELECT action, key_combo FROM keybinds")
    return {row["action"]: row["key_combo"] for row in rows}

def set_keybind(action: str, key_combo: str):
    execute_query("INSERT INTO keybinds (action, key_combo) VALUES (?, ?) ON CONFLICT(action) DO UPDATE SET key_combo=excluded.key_combo", (action, key_combo))

def clear_keybind(action: str):
    execute_query("DELETE FROM keybinds WHERE action = ?", (action,))
