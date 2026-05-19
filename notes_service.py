from storage import execute_query, fetch_one, fetch_all

def create_note(content: str, name: str | None = None, mode_id: int | None = None) -> int:
    cursor = execute_query(
        "INSERT INTO notes (name, content, mode_id) VALUES (?, ?, ?)",
        (name, content, mode_id)
    )
    return cursor.lastrowid

def append_to_note(note_id: int, content: str, separator: str = "\n"):
    execute_query(
        "UPDATE notes SET content = content || ? || ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (separator, content, note_id)
    )

def append_to_latest_note(content: str):
    row = fetch_one("SELECT id FROM notes ORDER BY created_at DESC LIMIT 1")
    if row:
        append_to_note(row["id"], content)
    else:
        create_note(content)

def get_latest_note_id() -> int | None:
    row = fetch_one("SELECT id FROM notes ORDER BY created_at DESC LIMIT 1")
    return row["id"] if row else None

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
    return fetch_one(
        "SELECT n.*, m.name as mode_name FROM notes n LEFT JOIN modes m ON n.mode_id = m.id WHERE n.id = ?",
        (note_id,)
    )

def get_note_by_name(name: str):
    return fetch_all(
        "SELECT n.*, m.name as mode_name FROM notes n LEFT JOIN modes m ON n.mode_id = m.id WHERE n.name = ?",
        (name,)
    )

def list_notes(limit: int = 50):
    return fetch_all(
        "SELECT n.*, m.name as mode_name FROM notes n LEFT JOIN modes m ON n.mode_id = m.id ORDER BY n.created_at DESC LIMIT ?",
        (limit,)
    )

def search_notes(query: str = None, mode: str = None, limit: int = 50) -> list:
    """Search notes by name, content, ID, and/or mode."""
    sql = "SELECT n.*, m.name as mode_name FROM notes n LEFT JOIN modes m ON n.mode_id = m.id WHERE 1=1"
    params = []
    if query:
        if query.strip().isdigit():
            sql += " AND (n.id = ? OR n.name LIKE ? OR n.content LIKE ?)"
            params.extend([int(query.strip()), f"%{query}%", f"%{query}%"])
        else:
            sql += " AND (n.name LIKE ? OR n.content LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
    if mode:
        sql += " AND m.name = ?"
        params.append(mode)
    sql += " ORDER BY n.created_at DESC LIMIT ?"
    params.append(limit)
    return fetch_all(sql, params)

def delete_note_by_id(note_id: int):
    execute_query("DELETE FROM notes WHERE id = ?", (note_id,))

def delete_notes_by_name(name: str):
    execute_query("DELETE FROM notes WHERE name = ?", (name,))
