"""Main TUI screen — note list with detail panel."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button
from textual.containers import Horizontal, Vertical
from textual.binding import Binding

import notes_service
import settings_service
import modes_service
import export_service

from tui.widgets.note_list import NoteList, NoteSelected
from tui.widgets.note_detail import NoteDetail
from tui.widgets.mode_bar import ModeBar
from tui.screens.editor import EditorScreen, RenameScreen
from tui.screens.export import ExportScreen


class MainScreen(Screen):
    """Main screen with note list, detail panel, and mode bar."""

    CSS = """
    MainScreen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr;
    }
    #left-panel {
        height: 100%;
        border-right: solid $primary;
    }
    #right-panel {
        height: 100%;
        overflow-y: auto;
    }
    #note-actions {
        dock: top;
        height: 3;
        padding: 0 1;
    }
    #note-actions Button {
        margin-right: 1;
        min-width: 10;
    }
    #search-bar {
        dock: top;
        height: 3;
        margin: 0 1;
    }
    #search-input {
        height: 3;
    }
    #mode-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    #note-detail {
        height: 100%;
        padding: 1 2;
        overflow-y: auto;
    }
    #header-info {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("n", "new_note", "New"),
        Binding("e", "edit_note", "Edit"),
        Binding("r", "rename_note", "Rename"),
        Binding("d", "delete_note", "Delete"),
        Binding("/", "focus_search", "Search"),
        Binding("c", "copy_note", "Copy"),
        Binding("x", "export_note", "Export"),
        Binding("[", "mode_prev", "Mode ◀"),
        Binding("]", "mode_next", "Mode ▶"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "clear_search", "Clear search"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._search_active = False
        self._selected_note_id: int | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="left-panel"):
            with Horizontal(id="search-bar"):
                yield Input(placeholder="Search notes... (press /)", id="search-input")
            yield NoteList(id="note-list")
            yield ModeBar(id="mode-bar")

        with Vertical(id="right-panel"):
            with Horizontal(id="note-actions"):
                yield Button("New", variant="primary", id="new-note-btn")
                yield Button("Edit", id="edit-note-btn")
                yield Button("Rename", id="rename-note-btn")
                yield Button("Delete", variant="error", id="delete-note-btn")
            yield NoteDetail(id="note-detail")

        yield Footer()

    async def on_mount(self) -> None:
        await self._refresh_notes()

    async def _refresh_notes(self, query: str | None = None, selected_note_id: int | None = None) -> None:
        """Load notes into the list."""
        if query:
            notes = notes_service.search_notes(query=query, limit=200)
        else:
            notes = notes_service.list_notes(limit=200)
        selected_note_id = selected_note_id or self._selected_note_id
        await self.query_one("#note-list", NoteList).update_notes(notes, selected_note_id=selected_note_id)
        if notes:
            ids = [note["id"] for note in notes]
            if selected_note_id in ids:
                self._selected_note_id = selected_note_id
            else:
                self._selected_note_id = notes[0]["id"]
            self.query_one("#note-detail", NoteDetail).note_data = notes_service.get_note(self._selected_note_id)
        else:
            self._selected_note_id = None
            self.query_one("#note-detail", NoteDetail).note_data = None

    # ── Note selection ──────────────────────────────────────────────────────

    def on_note_selected(self, event: NoteSelected) -> None:
        note = notes_service.get_note(event.note_id)
        self._selected_note_id = event.note_id
        self.query_one("#note-detail", NoteDetail).note_data = note

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-note-btn":
            self.action_new_note()
        elif event.button.id == "edit-note-btn":
            self.action_edit_note()
        elif event.button.id == "rename-note-btn":
            self.action_rename_note()
        elif event.button.id == "delete-note-btn":
            await self.action_delete_note()

    # ── Search ──────────────────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        self.set_focus(search_input)

    async def action_clear_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.value = ""
        await self._refresh_notes()
        self.query_one("#note-list", NoteList).focus()

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            query = event.value.strip()
            await self._refresh_notes(query if query else None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.query_one("#note-list", NoteList).focus()

    # ── CRUD actions ───────────────────────────────────────────────────────

    def action_new_note(self) -> None:
        before_ids = {note["id"] for note in notes_service.list_notes(limit=1000)}

        def on_result(created: bool):
            if created:
                after_notes = notes_service.list_notes(limit=1000)
                created_note = next((note for note in after_notes if note["id"] not in before_ids), None)
                self.run_worker(
                    self._refresh_notes(selected_note_id=created_note["id"] if created_note else None),
                    exclusive=True,
                )
        self.app.push_screen(EditorScreen(note_id=None), on_result)

    def action_edit_note(self) -> None:
        note_id = self._current_note_id()
        if not note_id:
            self.app.bell()
            return

        def on_result(saved: bool):
            if saved:
                self.run_worker(self._refresh_notes(selected_note_id=note_id), exclusive=True)
        self.app.push_screen(EditorScreen(note_id=note_id), on_result)

    def action_rename_note(self) -> None:
        note_id = self._current_note_id()
        if not note_id:
            self.app.bell()
            return

        def on_result(saved: bool):
            if saved:
                self.run_worker(self._refresh_notes(selected_note_id=note_id), exclusive=True)
                self.app.notify("Note renamed", severity="information")

        self.app.push_screen(RenameScreen(note_id=note_id), on_result)

    async def action_delete_note(self) -> None:
        note_id = self._current_note_id()
        if not note_id:
            self.app.bell()
            return
        notes_service.delete_note_by_id(note_id)
        self._selected_note_id = None
        await self._refresh_notes()

    def action_copy_note(self) -> None:
        note_id = self._current_note_id()
        if not note_id:
            self.app.bell()
            return
        ok = export_service.export_note_to_clipboard(note_id)
        if ok:
            self.app.notify("Copied to clipboard", severity="information")
        else:
            self.app.notify("Failed to copy", severity="error")

    def action_export_note(self) -> None:
        note_id = self._current_note_id()

        def on_result(success: bool):
            if success:
                self.app.notify("Export complete", severity="information")
            else:
                self.app.notify("Export failed", severity="error")

        self.app.push_screen(ExportScreen(selected_note_id=note_id), on_result)

    def _current_note_id(self) -> int | None:
        note_list = self.query_one("#note-list", NoteList)
        return note_list.get_selected_note_id() or self._selected_note_id

    # ── Mode cycling ───────────────────────────────────────────────────────

    def action_mode_prev(self) -> None:
        mode_bar = self.query_one("#mode-bar", ModeBar)
        mode_bar.cycle(-1)

    def action_mode_next(self) -> None:
        mode_bar = self.query_one("#mode-bar", ModeBar)
        mode_bar.cycle(1)

    # ── Quit ───────────────────────────────────────────────────────────────

    def action_quit(self) -> None:
        self.app.exit()
