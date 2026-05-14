# KeyNote Feature Implementation Plan

## Overview

Four major feature areas to implement:

1. **Mode cycling shortcuts** — Replace per-mode hotkeys with up/down cycling
2. **Compact overlay with mode indicator** — Smaller text, persistent mode display with highlight
3. **Search** — Fix the broken search by name, content, and ID
4. **TUI** — Full terminal UI for viewing, searching, editing, managing, recording, and exporting notes
5. **Export** — Per-note and bulk export to clipboard / JSON / Markdown / text

---

## 1. Mode Cycling Shortcuts

### Problem
Current: each mode gets its own hotkey (`Ctrl+Alt+1` through `Ctrl+Alt+7`). This doesn't scale — adding a mode requires manually binding a new key.

### Solution
Two new global hotkeys that cycle through the mode list:

| Action | Default Key | Behavior |
|--------|-------------|----------|
| `mode_prev` | `Ctrl+Alt+,` | Switch to previous mode (wraps around) |
| `mode_next` | `Ctrl+Alt+.` | Switch to next mode (wraps around) |

### Implementation Steps

- [ ] **1.1** Add `mode_prev` and `mode_next` actions to `migrations.py` bootstrap defaults
- [ ] **1.2** Remove individual `mode:<name>` keybind defaults from `migrations.py` (keep them if user manually added, but don't seed them)
- [ ] **1.3** Add `cycle_mode(direction: int)` function to `modes_service.py`:
  - Get current active mode from settings
  - Get ordered list of all modes
  - Find current index, apply `+1` or `-1` with wrap-around
  - Set new active mode
  - Return new mode name
- [ ] **1.4** Update `keynote_ptt.py` `main()` to register `mode_prev`/`mode_next` hotkeys calling `cycle_mode(-1)` / `cycle_mode(1)`
- [ ] **1.5** Keep existing `mode:<name>` bind support for backward compat — if user has them in DB they still work, but we no longer seed them
- [ ] **1.6** Update `cli.py` mode bind command docs — note that cycling is the default but individual mode binds still work
- [ ] **1.7** Update `keybind set` to accept `mode_prev` / `mode_next` as valid actions

### Files Modified
- `migrations.py` — new defaults
- `modes_service.py` — `cycle_mode()`
- `keynote_ptt.py` — hotkey registration
- `cli.py` — minor doc updates

---

## 2. Compact Overlay with Mode Indicator

### Problem
Current overlay: `Segoe UI 11pt bold`, `padx=15, pady=10`, only shows transient messages. No persistent indication of which mode is active. Too large.

### Solution
Redesign the overlay to be:
- **Much smaller** — 8pt font, minimal padding
- **Persistent mode bar** — Always visible (not transient), shows the active mode name highlighted
- **Transient notifications** — Brief messages (recording, saved, etc.) appear above the mode bar and auto-dismiss

### Design

```
┌─────────────────────────┐
│ ⏺ REC                   │  ← transient, auto-hides
│ ▸ slack                 │  ← persistent mode bar
└─────────────────────────┘
```

When cycling modes:
```
┌──────────────┐
│ ▸ translate   │  ← highlighted/active mode
└──────────────┘
```

### Implementation Steps

- [ ] **2.1** Redesign `OverlayManager` to have two sections:
  - **Mode bar** (bottom, always visible) — shows active mode name
  - **Notification bar** (above mode bar, transient) — shows recording/saved/etc messages
- [ ] **2.2** Reduce font size to `Segoe UI 8` or `Consolas 8`
- [ ] **2.3** Reduce padding to `padx=6, pady=3`
- [ ] **2.4** Reduce opacity slightly (`0.80`) for less visual intrusion
- [ ] **2.5** Add `update_mode_display(mode_name)` method that updates the persistent mode bar
- [ ] **2.6** Highlight active mode with a distinct color (e.g., `#4fc3f7` light blue for active mode name, vs `#888888` gray for label)
- [ ] **2.7** Call `overlay.update_mode_display()` on startup and after every `set_mode()` / `cycle_mode()` call
- [ ] **2.8** Position overlay at bottom-right but closer to corner (10px from right, 10px from bottom)
- [ ] **2.9** When overlay first starts, query current active mode and display it

### Files Modified
- `keynote_ptt.py` — `OverlayManager` class rewrite, `set_mode()` / `cycle_mode()` integration

---

## 3. Search Feature

### Problem
Current `note list --query` is ignored. `note list --mode` is ignored. No search functionality exists.

### Solution
Implement search across note name, content, and ID. Search should be:
- **By name** — substring match (case-insensitive)
- **By content** — substring match (case-insensitive)
- **By ID** — exact match if query is a number
- **By mode** — filter by mode name

### Implementation Steps

- [ ] **3.1** Add `search_notes(query, mode=None, limit=50)` to `notes_service.py`:
  ```python
  def search_notes(query: str = None, mode: str = None, limit: int = 50) -> list[dict]:
      sql = "SELECT n.*, m.name as mode_name FROM notes n LEFT JOIN modes m ON n.mode_id = m.id WHERE 1=1"
      params = []
      if query:
          # If query looks like a number, also match by ID
          if query.isdigit():
              sql += " AND (n.id = ? OR n.name LIKE ? OR n.content LIKE ?)"
              params.extend([int(query), f"%{query}%", f"%{query}%"])
          else:
              sql += " AND (n.name LIKE ? OR n.content LIKE ?)"
              params.extend([f"%{query}%", f"%{query}%"])
      if mode:
          sql += " AND m.name = ?"
          params.append(mode)
      sql += " ORDER BY n.created_at DESC LIMIT ?"
      params.append(limit)
      return fetch_all(sql, params)
  ```
- [ ] **3.2** Update `cli.py` `note list` to use `search_notes()` instead of `list_notes()` when `--query` or `--mode` is provided
- [ ] **3.3** Display search results with mode name, not just mode_id
- [ ] **3.4** Add `keynote note search <query>` as an alias/symlink to `note list --query` for discoverability

### Files Modified
- `notes_service.py` — `search_notes()`
- `cli.py` — `note list` and new `note search`

---

## 4. TUI (Terminal User Interface)

### Problem
No interactive TUI exists. All management is through CLI commands. No way to browse, edit, or record notes interactively.

### Solution
Build a TUI using **Textual** (Python TUI framework — async, widget-based, well-maintained, already in the Python ecosystem). The TUI should be a separate entrypoint `keynote-tui` or a subcommand `keynote tui`.

### TUI Layout

```
┌─ KeyNote ────────────────────────────────────────────────────┐
│ [Search: ________]  Mode: ▸ slack  [Autopaste: OFF]         │
├──────────────────────────────────────────────────────────────┤
│  Notes                                        │  Detail      │
│  ┌──────────────────────────────────────┐     │  ┌─────────┐│
│  │ > 1  Slack msg to team    slack  12:3│     │  │ Name:   ││
│  │   2  Email to client      mail   11:2│     │  │ Slk msg ││
│  │   3  Meeting notes        transc 10:0│     │  │         ││
│  │   4  Quick thought        (none) 9:45│     │  │ Content:││
│  │   ...                                │     │  │ Hey te..││
│  │                                      │     │  │ ...     ││
│  └──────────────────────────────────────┘     │  │         ││
│                                               │  │ [Edit]  ││
│  [n]New [e]Edit [d]Delete [/]Search [r]Record │  │ [Copy]  ││
│  [m]Mode [x]Export [q]Quit                    │  │ [Export] ││
│                                               │  └─────────┘│
└──────────────────────────────────────────────────────────────┘
```

### TUI Screens / Features

| Feature | Description |
|---------|-------------|
| **Note list** | Browse all notes with name, mode, timestamp. Scroll with arrows. |
| **Note detail** | Right panel shows full content of selected note. |
| **Search** | Filter notes by name, content, or ID (reuses `search_notes()`). Live filtering as you type. |
| **Edit** | Open an editor screen (Textual TextArea widget) to edit note content or name inline. |
| **New note** | Create a new note with name and content via a form. |
| **Delete** | Delete selected note with confirmation. |
| **Record** | Trigger recording (same as F8/F7) from within TUI — calls the PTT recording pipeline. |
| **Mode cycling** | Show current mode, cycle with `[` / `]` keys. |
| **Quick copy** | Press `c` to copy selected note to clipboard. |
| **Export** | Press `x` to export selected note (or all) to file (JSON/MD/TXT). |
| **Autopaste toggle** | Toggle autopaste from TUI header. |

### Implementation Steps

- [ ] **4.1** Add `textual` to `requirements.txt`
- [ ] **4.2** Create `tui/` package:
  ```
  tui/
  ├── __init__.py
  ├── app.py          # Main Textual App class
  ├── screens/
  │   ├── __init__.py
  │   ├── main.py     # Main screen (note list + detail)
  │   ├── editor.py   # Note editor screen
  │   ├── search.py   # Search screen (or inline)
  │   └── export.py   # Export dialog
  └── widgets/
      ├── __init__.py
      ├── note_list.py    # Note list widget
      ├── note_detail.py  # Note detail viewer
      └── mode_bar.py     # Mode indicator bar
  ```
- [ ] **4.3** Implement `tui/app.py` — `KeyNoteApp(TextualApp)`:
  - Header with mode display and autopaste toggle
  - Body: two-column layout (note list left, detail right)
  - Footer with keybinding hints
  - Load notes on mount, refresh on changes
- [ ] **4.4** Implement `widgets/note_list.py`:
  - `OptionList` or custom `ListItem`-based list
  - Each item shows: ID, name (or "Unnamed"), mode badge, relative time
  - Arrow keys navigate, Enter opens detail
  - Highlights selected note
- [ ] **4.5** Implement `widgets/note_detail.py`:
  - `Static` widget showing full note content
  - Shows: name, mode, created/updated timestamps, full content
  - Updates when note list selection changes
- [ ] **4.6** Implement `screens/editor.py`:
  - `TextArea` widget for editing note content
  - Input field for note name
  - Save (Ctrl+S) / Cancel (Escape) buttons
  - Pre-populated with existing note data when editing
- [ ] **4.7** Implement search — inline filter in the note list:
  - `/` key activates search input in header
  - As-you-type filtering using `search_notes()`
  - `Escape` clears filter
  - Shows result count
- [ ] **4.8** Implement recording from TUI:
  - `r` key starts recording (shows "Recording..." indicator)
  - `r` again stops recording
  - Uses `PushToTalkFormatter` recording methods
  - On completion, refreshes note list
- [ ] **4.9** Implement mode cycling in TUI:
  - `[` / `]` keys cycle modes (or dedicated buttons)
  - Header updates immediately
- [ ] **4.10** Implement quick clipboard copy:
  - `c` copies selected note content to clipboard
  - Shows brief toast notification
- [ ] **4.11** Implement export screen (see section 5 below)
- [ ] **4.12** Add TUI entrypoint:
  - `keynote tui` CLI subcommand in `cli.py`
  - Or standalone `keynote-tui` script
  - TUI runs in its own process (can connect to same DB)
- [ ] **4.13** Add TUI keybinding reference in footer:
  - `n` new, `e` edit, `d` delete, `/` search, `r` record, `c` copy, `x` export, `[`/`]` mode, `q` quit

### Files Created
- `tui/__init__.py`
- `tui/app.py`
- `tui/screens/__init__.py`
- `tui/screens/main.py`
- `tui/screens/editor.py`
- `tui/screens/export.py`
- `tui/widgets/__init__.py`
- `tui/widgets/note_list.py`
- `tui/widgets/note_detail.py`
- `tui/widgets/mode_bar.py`

### Files Modified
- `requirements.txt` — add `textual`
- `cli.py` — add `tui` subcommand

---

## 5. Export Feature

### Problem
No export capability exists. Notes can only be viewed on screen.

### Solution
Export notes individually or in bulk, to clipboard or to file.

### Export Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| **JSON** | `.json` | Array of note objects with all fields |
| **Markdown** | `.md` | Each note as an H2 section with metadata |
| **Text** | `.txt` | Plain text with simple separators |

### Export Scopes

| Scope | CLI | TUI |
|-------|-----|-----|
| **Single note → clipboard** | `keynote note export --id 5 --clipboard` | Press `c` on selected note |
| **Single note → file** | `keynote note export --id 5 --format md` | Export dialog → pick format |
| **All notes → file** | `keynote note export --all --format json` | Export dialog → "All notes" toggle |

### Format Details

**JSON** (`--format json`):
```json
[
  {
    "id": 1,
    "name": "Slack msg to team",
    "content": "Hey team...",
    "mode": "slack",
    "created_at": "2025-05-06 12:30:00",
    "updated_at": "2025-05-06 12:30:00"
  }
]
```

**Markdown** (`--format md`):
```markdown
## Slack msg to team

- **ID:** 1
- **Mode:** slack
- **Created:** 2025-05-06 12:30:00
- **Updated:** 2025-05-06 12:30:00

Hey team...
```

**Text** (`--format txt`):
```
=== Note #1: Slack msg to team ===
Mode: slack | Created: 2025-05-06 12:30:00

Hey team...
```

### Implementation Steps

- [ ] **5.1** Create `export_service.py` with:
  - `export_note_to_clipboard(note_id: int)` — copies note content to clipboard
  - `export_notes_to_file(note_ids: list[int] | None, format: str, output_path: str)` — exports one or all notes to file
    - If `note_ids` is `None`, export all notes
  - `format_notes_json(notes: list[dict]) -> str`
  - `format_notes_markdown(notes: list[dict]) -> str`
  - `format_notes_text(notes: list[dict]) -> str`
- [ ] **5.2** Add `note export` CLI command in `cli.py`:
  ```
  keynote note export --id 5 --clipboard
  keynote note export --id 5 --format md [--output notes.md]
  keynote note export --all --format json [--output keynote_export.json]
  ```
  - `--clipboard` only valid for single note
  - `--format` defaults to `json`
  - `--output` defaults to `keynote_export.{ext}` in current directory
  - `--all` exports all notes
- [ ] **5.3** Integrate quick copy (`c` key) in TUI using `export_note_to_clipboard()`
- [ ] **5.4** Implement export dialog in TUI (`screens/export.py`):
  - Radio buttons: selected note / all notes
  - Format selector: JSON / Markdown / Text
  - Output path input (with default)
  - "Export" button → writes file, shows success toast
- [ ] **5.5** Join mode name into note data for export (LEFT JOIN modes on mode_id)

### Files Created
- `export_service.py`

### Files Modified
- `cli.py` — `note export` command
- `tui/screens/export.py` — export dialog
- `tui/app.py` — wire up export keybinding

---

## Execution Order

Recommended implementation sequence:

1. **Search** (§3) — smallest scope, unblocks TUI
2. **Mode cycling** (§1) — needed before overlay redesign
3. **Compact overlay** (§2) — builds on mode cycling
4. **Export service** (§5) — needed before TUI export
5. **TUI** (§4) — depends on all above
6. **Integration testing** — verify everything works together

---

## Dependencies to Add

```
textual>=0.47.0
```

---

## Risk / Mitigation

| Risk | Mitigation |
|------|------------|
| Textual + tkinter overlay running simultaneously | They're in separate processes — no conflict. TUI is independent. |
| Recording from TUI requires audio thread | Reuse `PushToTalkFormatter` but start/stop programmatically instead of via hotkey. |
| Mode cycling + individual mode binds conflict | Both work — cycling is just a different way to trigger `set_mode()`. If user has both, the individual bind is a shortcut to a specific mode, cycling goes sequentially. |
| Large note lists in TUI | Use lazy loading / virtual scrolling (Textual `OptionList` handles this). |
| Export overwriting existing files | Check if file exists, prompt overwrite confirmation. |
