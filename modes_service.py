from storage import execute_query, fetch_one, fetch_all

def get_mode(name: str):
    return fetch_one("SELECT * FROM modes WHERE name = ?", (name,))

def list_modes():
    return fetch_all("SELECT * FROM modes ORDER BY name")

def add_mode(name: str, prompt: str):
    execute_query("INSERT INTO modes (name, system_prompt) VALUES (?, ?)", (name, prompt))

def set_mode_prompt(name: str, prompt: str):
    execute_query("UPDATE modes SET system_prompt = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?", (prompt, name))

def delete_mode(name: str):
    execute_query("DELETE FROM modes WHERE name = ?", (name,))
    
def get_mode_by_id(mode_id: int):
    return fetch_one("SELECT * FROM modes WHERE id = ?", (mode_id,))
