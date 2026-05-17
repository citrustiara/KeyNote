# KeyNote

KeyNote is mainly a test harness for audio-to-text capabilities in local multimodal LLMs served through `llama-server`. It can also function as a lightweight note app with basic recording, storage, mode prompts, search, export, and clipboard workflows.

---

## Features

- **Push-to-Talk Recording**: Hold a hotkey to record, release to process.
- **Local Audio-to-Text Testing**: Run audio through local multimodal models via `llama.cpp`'s `llama-server`.
- **Dynamic Prompt Modes**: Cycle between `slack`, `mail`, `summarize`, and more.
- **Smart SQLite Storage**: All notes are stored locally with metadata and search capabilities.
- **Auto-Paste**: Transcribed text can be automatically pasted into your active application.
- **CLI & TUI**: Manage notes, modes, settings, and exports from a command-line interface or terminal UI.

---

## Installation

This project uses `uv` for fast, reliable dependency management.

1. **Install `uv`** (if you haven't already):
   ```bash
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Install KeyNote globally** (as an editable tool):
   ```bash
   uv tool install --editable .
   ```

3. **Initialize the Database**:
   ```bash
   keynote note list
   # or run migrations directly
   python migrations.py
   ```

---

## Quick Start

1. **Start your `llama-server`**:
   Ensure you have a local server running with a multimodal model (like Whisper + LLM or a unified model).
   ```bash
   llama-server --model ... --port 8080
   ```

2. **Launch the KeyNote Service**:
   ```bash
   keynote start
   ```

3. **Record a Note**:
   - Hold **F8** to record a new note.
   - Hold **F7** to append to the latest or active note.
   - Transcribed text will be copied to your clipboard automatically.

---

## Hotkeys

| Action | Default Key | Description |
| :--- | :--- | :--- |
| `record_new_note` | `F8` | Record and save as a new note |
| `record_append_latest` | `F7` | Record and append to the active/latest note |
| `toggle_autopaste` | `Ctrl+Alt+V` | Toggle automatic pasting of results |
| `mode_prev` | `Ctrl+Alt+,` | Cycle to the previous mode |
| `mode_next` | `Ctrl+Alt+.` | Cycle to the next mode |
| `Alt+F1` | `Alt+F1` | Exit the PTT service |

Direct mode hotkeys such as `mode:slack` or `mode:transcript` are not bound by default. They remain optional and can be added manually with `keynote mode bind <name> --key <combo>` or `keynote keybind set mode:<name> <combo>`.

---

## CLI Command Reference

### Service & UI
- `keynote start` - Launch the PTT background service.
- `keynote tui` - Launch the interactive Terminal User Interface.

### Notes Management
- `keynote note add "text"` - Add a note manually.
- `keynote note list` - List recent notes.
- `keynote note search "query"` - Search notes by content or name.
- `keynote note enter --id <id>` - Set a note as "active" for appends.
- `keynote note export --id <id> --format md` - Export to Markdown.

### Mode & Settings
- `keynote mode list` - Show all available prompt modes.
- `keynote mode use <name>` - Switch the current active mode.
- `keynote keybind set <action> <key>` - Change a hotkey.
- `keynote settings set <key> <value>` - Update internal settings.

---

## TUI (Terminal User Interface)

Launch a beautiful, interactive interface to manage your notes and settings:
```bash
keynote tui
```

---

*KeyNote: Speak your mind, let AI do the typing.*
