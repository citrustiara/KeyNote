from storage import execute_query, fetch_one, fetch_all

def create_note(content: str, name: str | None = None, mode_id: int | None = None) -> int:
    cursor = execute_query(
        "INSERT INTO notes (name, content, mode_id) VALUES (?, ?, ?)",
        (name, content, mode_id)
    )
    return cursor.lastrowid

def append_to_note(note_id: int, content: str):
    execute_query(
        "UPDATE notes SET content = content || '\n' || ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (content, note_id)
    )

def append_to_latest_note(content: str):
    row = fetch_one("SELECT id FROM notes ORDER BY created_at DESC LIMIT 1")
    if row:
        append_to_note(row["id"], content)
    else:
        create_note(content)

def edit_note_content(note_id: int, content: str):
    execute_query(
        "UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (content, note_id)
    )

def rename_note(note_id: int, name: str):
    execute_query(
        "UPDATE notes SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (name, note_id)
    )

def get_note(note_id: int):
    return fetch_one("SELECT * FROM notes WHERE id = ?", (note_id,))

def get_note_by_name(name: str):
    return fetch_all("SELECT * FROM notes WHERE name = ?", (name,))

def list_notes(limit: int = 20):
    return fetch_all("SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,))

def delete_note_by_id(note_id: int):
    execute_query("DELETE FROM notes WHERE id = ?", (note_id,))

def delete_notes_by_name(name: str):
    execute_query("DELETE FROM notes WHERE name = ?", (name,))
