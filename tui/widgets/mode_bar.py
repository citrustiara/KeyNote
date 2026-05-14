"""Mode indicator bar widget for the TUI header."""

from textual.widgets import Static
from textual.reactive import reactive
import settings_service
import modes_service


class ModeBar(Static):
    """Persistent mode indicator showing the current active mode."""

    current_mode: reactive[str] = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_mode = settings_service.get_active_mode()

    def on_mount(self) -> None:
        self._refresh_display()

    def watch_current_mode(self, mode: str) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        mode = self.current_mode or "(no mode)"
        self.update(f"▸ [b #4fc3f7]{mode}[/]")

    def cycle(self, direction: int) -> str:
        """Cycle mode and update display. Returns new mode name."""
        new_mode = modes_service.cycle_mode(direction)
        self.current_mode = new_mode
        return new_mode
