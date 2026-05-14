"""Note editor screen — inline editing of note name and content."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, TextArea, Label, Static
from textual.containers import Vertical, Horizontal
import notes_service


class EditorScreen(ModalScreen[bool]):
    """Modal screen for creating or editing a note."""

    CSS = """
    EditorScreen {
        align: center middle;
    }
    #editor-container {
        width: 80%;
        height: 80%;
        max-width: 100;
        max-height: 35;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #editor-container Label {
        margin-top: 1;
    }
    #editor-container Input {
        margin-bottom: 1;
    }
    #editor-container TextArea {
        height: 1fr;
        margin-bottom: 1;
    }
    .button-row {
        height: 3;
        align: center middle;
    }
    .button-row Button {
        margin: 0 1;
        width: 12;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    def __init__(self, note_id: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.note_id = note_id
        self._note = None

    def compose(self) -> ComposeResult:
        with Vertical(id="editor-container"):
            yield Label("[b]Name:[/b]")
            yield Input(placeholder="Note name (optional)", id="name-input")
            yield Label("[b]Content:[/b]")
            yield TextArea("", id="content-area")
            with Horizontal(classes="button-row"):
                yield Button("Save [Ctrl+S]", variant="primary", id="save-btn")
                yield Button("Cancel [Esc]", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        if self.note_id:
            self._note = notes_service.get_note(self.note_id)
            if self._note:
                name_input = self.query_one("#name-input", Input)
                content_area = self.query_one("#content-area", TextArea)
                name_input.value = self._note["name"] or ""
                content_area.load_text(self._note["content"] or "")

    def action_save(self) -> None:
        self._save()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save()
        elif event.button.id == "cancel-btn":
            self.dismiss(False)

    def _save(self) -> None:
        name = self.query_one("#name-input", Input).value.strip() or None
        content = self.query_one("#content-area", TextArea).text

        if self.note_id:
            notes_service.edit_note_content(self.note_id, content)
            notes_service.rename_note(self.note_id, name or "")
        else:
            notes_service.create_note(content, name=name)

        self.dismiss(True)
