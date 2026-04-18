# KeyNote

Local push-to-talk formatter with a persistent local database, dynamic keybinds, robust CLI, and prompt modes. Backed by `llama.cpp` and SQLite.

## What it does
- Press or hold your bound keys (e.g. `F8` or `F7`) to record microphone audio
- Release the key to transcribe via local API (`llama-server`)
- Formats output using selected prompt mode (e.g. `slack`, `email`, `requirements`)
- Automatically saves your notes to a local SQLite database
- Supports creating new notes or appending to your active/latest note
- Auto-paste toggle to automatically type out the transcribed text

## Setup and Migration

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the database migrations (this will create `keynote.db`, import your legacy prompts, and set default keybinds):
```bash
python migrations.py
```

## Running the app

Start the runtime daemon:
```bash
python keynote_ptt.py --server-url http://localhost:8080
```
*(Make sure your `llama-server` is running locally at the specified URL)*

## CLI Command Reference

We provide a Typer-backed CLI via `cli.py` (`python cli.py [COMMAND]`).

### Notes commands
- `python cli.py note add "text" [--name "..."] [--mode <name>]`
- `python cli.py note list [--limit 20]`
- `python cli.py note show --id <id>`
- `python cli.py note edit "new text" --id <id>`
- `python cli.py note rename --id <id> --name "new-name"`
- `python cli.py note append "appended text" --id <id>`
- `python cli.py note delete --id <id>`

**Active Note Semantics:**
- You can "enter" a note to make it active: `python cli.py note enter --id <id>`
- When an active note is set, the append hotkey (e.g. `F7`) will add transcriptions to that active note.
- If no active note is set, `F7` will append to the *most recently created* note.
- Leave the active note context: `python cli.py note leave`

### Mode commands
- `python cli.py mode list`
- `python cli.py mode add <name> --prompt "..."` / `--prompt-file path.txt`
- `python cli.py mode use <name>` (activates the mode for recording)
- `python cli.py mode bind <name> --key "ctrl+alt+num"`

### Keybind commands
Default binds:
- `record_new_note`: `f8`
- `record_append_latest`: `f7`
- `toggle_autopaste`: `ctrl+alt+v`

Manage them list this:
- `python cli.py keybind list`
- `python cli.py keybind set record_new_note f8`
- `python cli.py keybind clear <action>`
(You must restart `keynote_ptt.py` after changing hotkeys for now).

### Autopaste commands
When autopaste is enabled, KeyNote will emit an OS-level paste key combination (`Ctrl+V` on Win/Linux, `Cmd+V` on Mac) after generating the text.
- `python cli.py autopaste on`
- `python cli.py autopaste off`
- `python cli.py autopaste toggle`
- `python cli.py autopaste status`

You can also use the default keybind `ctrl+alt+v` to toggle autopaste while the daemon runs.
