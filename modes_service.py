from storage import execute_query, fetch_one, fetch_all
import settings_service
from pathlib import Path

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

def cycle_mode(direction: int) -> str:
    """Cycle through modes. direction=1 for next, -1 for previous. Returns new mode name."""
    modes = list_modes()
    if not modes:
        return settings_service.get_active_mode()
    
    current = settings_service.get_active_mode()
    names = [m["name"] for m in modes]
    
    try:
        idx = names.index(current)
    except ValueError:
        idx = 0
    
    new_idx = (idx + direction) % len(names)
    new_mode = names[new_idx]
    settings_service.set_active_mode(new_mode)
    return new_mode


def sync_workflows():
    prompts_dir = Path("prompts")
    if not prompts_dir.exists():
        prompts_dir.mkdir()
        
    # 1. Sync from files to DB
    for prompt_file in prompts_dir.glob("*.md"):
        name = prompt_file.stem
        content = prompt_file.read_text(encoding="utf-8").strip()
        
        existing = get_mode(name)
        if existing:
            if existing["system_prompt"].strip() != content:
                set_mode_prompt(name, content)
        else:
            add_mode(name, content)
            
    # 2. Sync from DB to files (DB has priority - missing files are restored)
    all_modes = list_modes()
    for mode in all_modes:
        mode_name = mode["name"]
        mode_prompt = mode["system_prompt"]
        file_path = prompts_dir / f"{mode_name}.md"
        
        if not file_path.exists():
            file_path.write_text(mode_prompt, encoding="utf-8")

