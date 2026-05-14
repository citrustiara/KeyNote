"""Export notes to clipboard or file in JSON / Markdown / Text formats."""

import json
import pyperclip
from pathlib import Path
from notes_service import get_note, list_notes


def export_note_to_clipboard(note_id: int) -> bool:
    """Copy a single note's content to clipboard. Returns True on success."""
    note = get_note(note_id)
    if not note:
        return False
    pyperclip.copy(note["content"])
    return True


def format_notes_json(notes: list[dict]) -> str:
    """Format notes as a JSON array."""
    items = []
    for n in notes:
        items.append({
            "id": n["id"],
            "name": n["name"],
            "content": n["content"],
            "mode": n.get("mode_name"),
            "created_at": str(n["created_at"]),
            "updated_at": str(n["updated_at"]),
        })
    return json.dumps(items, indent=2, ensure_ascii=False)


def format_notes_markdown(notes: list[dict]) -> str:
    """Format notes as Markdown sections."""
    parts = []
    for n in notes:
        name = n["name"] or f"Note #{n['id']}"
        parts.append(f"## {name}\n")
        parts.append(f"- **ID:** {n['id']}")
        parts.append(f"- **Mode:** {n.get('mode_name') or '(none)'}")
        parts.append(f"- **Created:** {n['created_at']}")
        parts.append(f"- **Updated:** {n['updated_at']}")
        parts.append(f"\n{n['content']}\n")
    return "\n".join(parts)


def format_notes_text(notes: list[dict]) -> str:
    """Format notes as plain text."""
    parts = []
    for n in notes:
        name = n["name"] or f"Note #{n['id']}"
        mode = n.get("mode_name") or "(none)"
        parts.append(f"=== Note #{n['id']}: {name} ===")
        parts.append(f"Mode: {mode} | Created: {n['created_at']}\n")
        parts.append(n["content"])
        parts.append("")
    return "\n".join(parts)


_FORMATTERS = {
    "json": format_notes_json,
    "md": format_notes_markdown,
    "markdown": format_notes_markdown,
    "txt": format_notes_text,
    "text": format_notes_text,
}

_EXTENSIONS = {
    "json": ".json",
    "md": ".md",
    "markdown": ".md",
    "txt": ".txt",
    "text": ".txt",
}


def export_notes_to_file(
    note_ids: list[int] | None,
    format: str,
    output_path: str | None = None,
) -> str:
    """Export notes to a file. If note_ids is None, export all.
    Returns the path written to."""
    fmt = format.lower()
    if fmt not in _FORMATTERS:
        raise ValueError(f"Unknown format: {format!r}. Use: json, md, txt")

    if note_ids:
        notes = [get_note(nid) for nid in note_ids]
        notes = [n for n in notes if n is not None]
    else:
        notes = list_notes(limit=10000)

    if not notes:
        raise ValueError("No notes to export.")

    ext = _EXTENSIONS[fmt]
    if not output_path:
        output_path = f"keynote_export{ext}"

    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"File already exists: {output_path}")

    content = _FORMATTERS[fmt](notes)
    path.write_text(content, encoding="utf-8")
    return str(path)
