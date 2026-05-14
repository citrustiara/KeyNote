"""Export dialog screen — choose scope, format, and output path."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal
import export_service



class ExportScreen(ModalScreen[bool]):
    """Modal dialog for exporting notes."""

    CSS = """
    ExportScreen {
        align: center middle;
    }
    #export-container {
        width: 60%;
        max-width: 60;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #export-container Label {
        margin-top: 1;
    }
    #export-container Input {
        margin-bottom: 1;
    }
    RadioSet {
        height: auto;
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
    ]

    def __init__(self, selected_note_id: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.selected_note_id = selected_note_id

    def compose(self) -> ComposeResult:
        with Vertical(id="export-container"):
            yield Label("[b]Scope:[/b]")
            with RadioSet(id="scope-radio"):
                if self.selected_note_id:
                    yield RadioButton("Selected note", value=True, id="scope-selected")
                yield RadioButton("All notes", value=not bool(self.selected_note_id), id="scope-all")

            yield Label("[b]Format:[/b]")
            with RadioSet(id="format-radio"):
                yield RadioButton("JSON", value=True, id="fmt-json")
                yield RadioButton("Markdown", id="fmt-md")
                yield RadioButton("Text", id="fmt-txt")

            yield Label("[b]Output path:[/b]")
            yield Input("keynote_export.json", id="output-input")

            with Horizontal(classes="button-row"):
                yield Button("Export", variant="primary", id="export-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Update default output path when format changes."""
        if event.radio_set.id == "format-radio":
            output_input = self.query_one("#output-input", Input)
            if event.pressed.id == "fmt-json":
                output_input.value = "keynote_export.json"
            elif event.pressed.id == "fmt-md":
                output_input.value = "keynote_export.md"
            elif event.pressed.id == "fmt-txt":
                output_input.value = "keynote_export.txt"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-btn":
            self._do_export()
        elif event.button.id == "cancel-btn":
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _do_export(self) -> None:
        # Determine scope
        scope_set = self.query_one("#scope-radio", RadioSet)
        is_all = any(
            rb.id == "scope-all" and rb.value
            for rb in scope_set.query(RadioButton)
        )
        note_ids = None if is_all else [self.selected_note_id]

        # Determine format
        format_set = self.query_one("#format-radio", RadioSet)
        fmt = "json"
        for rb in format_set.query(RadioButton):
            if rb.value:
                if rb.id == "fmt-md":
                    fmt = "md"
                elif rb.id == "fmt-txt":
                    fmt = "txt"
                break

        output_path = self.query_one("#output-input", Input).value

        try:
            path = export_service.export_notes_to_file(note_ids, fmt, output_path)
            self.dismiss(True)
        except (ValueError, FileExistsError):
            self.dismiss(False)
