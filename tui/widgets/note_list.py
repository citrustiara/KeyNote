"""Note list widget — displays notes with name, mode, and timestamp."""

from textual.widgets import ListView, ListItem, Static
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text
from datetime import datetime


def _relative_time(dt_str: str) -> str:
    """Convert a datetime string to a human-readable relative time."""
    if not dt_str:
        return ""
    try:
        # Handle both "2025-05-06 12:30:00" and ISO formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(str(dt_str), fmt)
                break
            except ValueError:
                continue
        else:
            return str(dt_str)

        delta = datetime.now() - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except Exception:
        return str(dt_str)


class NoteSelected(Message):
    """Fired when a note is selected in the list."""
    def __init__(self, note_id: int) -> None:
        self.note_id = note_id
        super().__init__()


class NoteList(ListView):
    """A scrollable list of notes."""

    BINDINGS = [
        ("enter", "select_cursor", "View note"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._notes: list[dict] = []
        self._selected_id: int | None = None

    async def update_notes(self, notes: list[dict], selected_note_id: int | None = None) -> None:
        """Replace the note list content."""
        self._notes = notes
        await self.clear()
        for note in notes:
            item = self._make_item(note)
            await self.append(item)
        if notes:
            ids = [note["id"] for note in notes]
            if selected_note_id in ids:
                self._selected_id = selected_note_id
                self.index = ids.index(selected_note_id)
            else:
                self._selected_id = notes[0]["id"]
                self.index = 0
        else:
            self._selected_id = None

    def _make_item(self, note: dict) -> ListItem:
        nid = note["id"]
        name = note["name"] or "Unnamed"
        mode = note.get("mode_name") or "—"
        time_str = _relative_time(note.get("created_at"))

        # Truncate name for display
        display_name = name[:25] + "…" if len(name) > 25 else name
        label = f" {nid:<4} {display_name:<26} {mode:<12} {time_str}"

        item = ListItem(Static(label), id=f"note-{nid}")
        return item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """When user selects a note, fire NoteSelected message."""
        item_id = event.item.id
        if item_id and item_id.startswith("note-"):
            note_id = int(item_id.replace("note-", ""))
            self._selected_id = note_id
            self.post_message(NoteSelected(note_id))

    def get_selected_note_id(self) -> int | None:
        """Return the currently highlighted note ID."""
        if self._notes and self.index is not None and 0 <= self.index < len(self._notes):
            return self._notes[self.index]["id"]
        return self._selected_id
