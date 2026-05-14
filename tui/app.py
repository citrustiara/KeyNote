"""KeyNote TUI — interactive terminal interface for managing notes."""

from textual.app import App
from tui.screens.main import MainScreen


class KeyNoteApp(App):
    """KeyNote Terminal User Interface."""

    TITLE = "KeyNote"
    CSS = """
    Screen {
        background: $surface;
    }
    """

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
