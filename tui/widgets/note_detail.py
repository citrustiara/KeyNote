"""Note detail viewer — shows full content of a selected note."""

from textual.widgets import Static, Button
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from rich.markdown import Markdown
from rich.text import Text


class NoteDetail(Vertical):
    """Right panel showing the full note content."""

    note_data: reactive[dict | None] = reactive(None)

    def compose(self):
        yield Static("[b]Select a note[/b]", id="detail-content")

    def watch_note_data(self, new_data: dict | None) -> None:
        """Update display when note_data changes."""
        content_widget = self.query_one("#detail-content", Static)
        if not new_data:
            content_widget.update("[dim]Select a note from the list[/dim]")
            return

        name = new_data.get("name") or "Unnamed"
        mode = new_data.get("mode_name") or "—"
        created = new_data.get("created_at", "")
        updated = new_data.get("updated_at", "")
        content = new_data.get("content", "")

        header = f"[b]{name}[/b]\n"
        header += f"[dim]Mode:[/dim] {mode}  [dim]Created:[/dim] {created}\n"
        if updated != created:
            header += f"[dim]Updated:[/dim] {updated}\n"
        header += "─" * 40 + "\n"

        content_widget.update(header + content)
