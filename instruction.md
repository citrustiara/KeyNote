# KeyNote Senior Engineering Plan

## 1. Goal
Build a production-ready local note capture system around the current push-to-talk app, with:
- SQLite-backed persistence for notes, modes, settings, and keybinds
- Full CLI for creating, editing, deleting, selecting, and listing notes
- Configurable modes/system prompts and per-mode keybinds
- Auto-paste toggle (via keybind + CLI)
- Recording behavior:
  - **F8**: create a **new note** from latest transcription
  - **Hold F7**: append transcription to **latest note** (or active note if selected)

---

## 2. Scope

### In scope
1. Persistent local database (SQLite)
2. Runtime hotkey manager with dynamic action routing
3. CLI command surface for note/mode/keybind/settings management
4. Auto-paste setting and runtime toggle
5. Prompt-mode system stored in DB (not hardcoded only)
6. Migration path from file prompts and existing defaults

### Out of scope (v1)
- Cloud sync
- Multi-user auth
- GUI editor
- Rich text/markdown rendering engine

---

## 3. Architecture

## 3.1 Modules
- `keynote_ptt.py` (entrypoint/runtime loop)
- `storage.py` (SQLite connection + repositories)
- `migrations.py` (schema migration runner)
- `hotkeys.py` (register/unregister keybindings)
- `notes_service.py` (business logic for create/append/edit/delete/select)
- `modes_service.py` (mode CRUD + active mode)
- `settings_service.py` (autopaste and generic settings)
- `cli.py` (argparse/typer command tree)
- `autopaste.py` (OS-specific paste trigger abstraction)

## 3.2 Runtime flow
1. Hotkey press starts recording (`record_new_note` or `record_append_latest` action context)
2. Hotkey release stops recording and transcribes via local llama-server
3. Result is saved to DB according to action:
   - New note
   - Append to latest note
   - Append to selected active note (if any)
4. Result copied to clipboard
5. If `autopaste_enabled=true`, emit OS paste key combo

---

## 4. Database design (SQLite)

## 4.1 Schema v1

### `notes`
- `id INTEGER PRIMARY KEY`
- `name TEXT` *(nullable, indexed)*
- `content TEXT NOT NULL`
- `mode_id INTEGER NULL`
- `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`
- `updated_at DATETIME DEFAULT CURRENT_TIMESTAMP`

Indexes:
- `CREATE INDEX idx_notes_name ON notes(name);`
- `CREATE INDEX idx_notes_created_at ON notes(created_at DESC);`

### `modes`
- `id INTEGER PRIMARY KEY`
- `name TEXT UNIQUE NOT NULL`
- `system_prompt TEXT NOT NULL`
- `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`
- `updated_at DATETIME DEFAULT CURRENT_TIMESTAMP`

### `settings`
- `key TEXT PRIMARY KEY`
- `value TEXT NOT NULL`

Required keys:
- `active_mode`
- `autopaste_enabled` (`true/false`)
- `active_note_id` *(nullable)*

### `keybinds`
- `action TEXT PRIMARY KEY`
- `key_combo TEXT NOT NULL`

Action examples:
- `record_new_note`
- `record_append_latest`
- `toggle_autopaste`
- `mode:<mode_name>`

## 4.2 Bootstrap defaults
On first run:
- Seed modes from existing prompt files (`prompts/*.txt`)
- Seed keybinds:
  - `record_new_note = f8`
  - `record_append_latest = f7`
  - `toggle_autopaste = ctrl+alt+v`
- Seed settings:
  - `autopaste_enabled=false`
  - `active_mode=slack` (or first available)

---

## 5. CLI specification

Binary name examples use `keynote`.

## 5.1 Notes commands

### Create/add
- `keynote note add --text "..." [--name "..."] [--mode <name>]`

### List/show
- `keynote note list [--limit 20] [--mode <name>] [--query <text>]`
- `keynote note show --id <id>`
- `keynote note show --name "<name>"`

### Edit/update
- `keynote note edit --id <id> --text "..."`
- `keynote note edit --name "<name>" --text "..."`
- `keynote note rename --id <id> --name "new-name"`
- `keynote note append --id <id> --text "..."`
- `keynote note append --name "<name>" --text "..."`

### Delete
- `keynote note delete --id <id> [--yes]`
- `keynote note delete --name "<name>" [--all] [--yes]`

### Enter/select active note (id/name)
- `keynote note enter --id <id>`
- `keynote note enter --name "<name>"`
- `keynote note current`
- `keynote note leave`

Behavior:
- If `active_note_id` is set, append action targets active note.
- If not set, append action targets latest note.

Validation:
- `--id` and `--name` are mutually exclusive
- Duplicate name with no `--all` causes explicit error + candidates

## 5.2 Mode commands
- `keynote mode list`
- `keynote mode add <name> --prompt "..."`
- `keynote mode add <name> --prompt-file path.txt`
- `keynote mode set-prompt <name> --prompt "..."`
- `keynote mode set-prompt <name> --prompt-file path.txt`
- `keynote mode use <name>`
- `keynote mode delete <name>` *(protect active mode unless forced)*
- `keynote mode bind <name> --key "ctrl+alt+5"`

## 5.3 Keybind commands
- `keynote keybind list`
- `keynote keybind set record_new_note f8`
- `keynote keybind set record_append_latest f7`
- `keynote keybind set toggle_autopaste ctrl+alt+v`
- `keynote keybind clear <action>`

## 5.4 Settings/autopaste commands
- `keynote settings get <key>`
- `keynote settings set <key> <value>`
- `keynote autopaste on`
- `keynote autopaste off`
- `keynote autopaste toggle`
- `keynote autopaste status`

---

## 6. Hotkey and runtime behavior

## 6.1 Core key behavior
- **F8 press**: start recording context=`new_note`
- **F8 release**: transcribe -> create new note
- **F7 press**: start recording context=`append_note`
- **F7 release**: transcribe -> append to active note or latest note

## 6.2 Runtime mode switching
- Load `mode:<name>` actions from `keybinds`
- On hotkey press, set active mode in settings and print runtime feedback

## 6.3 Auto-paste behavior
After clipboard copy:
- if enabled, emit paste combo:
  - Windows/Linux: `Ctrl+V`
  - macOS: `Cmd+V`
- keybind and CLI toggle must stay in sync via DB-backed setting

## 6.4 Safety controls
- Reject duplicate key combos across actions unless explicitly forced
- Show conflict diagnostics
- Unregister/re-register hotkeys when keybinds change

---

## 7. Implementation plan by phase

## Phase 1 — Persistence foundation
- Add migration runner and schema v1
- Implement repositories for notes/modes/settings/keybinds
- Bootstrap defaults and import existing prompts

Deliverables:
- `storage.py`, `migrations.py`
- `keynote.db` auto-created

## Phase 2 — Runtime integration
- Refactor transcription output routing into action handlers
- Implement new-note and append-note logic
- Introduce active note semantics

Deliverables:
- Updated `keynote_ptt.py`
- `notes_service.py`

## Phase 3 — Autopaste
- Add setting read/write and runtime toggle action
- Implement OS-aware paste abstraction

Deliverables:
- `autopaste.py`
- hotkey + CLI toggle support

## Phase 4 — CLI v1
- Add commands for notes, modes, keybinds, settings
- Include delete/edit/enter-by-id-or-name support
- Add strict input validation and human-readable errors

Deliverables:
- `cli.py`
- README command docs

## Phase 5 — Dynamic hotkey manager
- Build centralized key registration
- Support mode keybinds and conflict detection
- Optional hot reload of keybinds

Deliverables:
- `hotkeys.py`

## Phase 6 — QA, tests, hardening
- Unit tests for CRUD, settings, keybind conflicts
- Integration tests with mocked inference
- Manual QA matrix

Deliverables:
- test suite + release checklist

---

## 8. Acceptance criteria

1. Notes persist after restart in SQLite
2. F8 always creates a new note from transcription
3. F7 always appends to active note, otherwise latest note
4. CLI can add/edit/delete/show/list notes by id and by name
5. CLI can enter/select/leave active note by id or name
6. Modes and system prompts are CRUD-manageable from CLI
7. Keybinds can be changed from CLI and applied to runtime actions
8. Auto-paste can be toggled by keybind and CLI and works cross-platform
9. Errors are deterministic and actionable (duplicate names/conflicting keybinds/invalid IDs)

---

## 9. Risks and mitigations
- **Hotkey conflicts**: enforce validation + explicit conflict reporting
- **Name ambiguity**: support `--all` for delete, otherwise require id or fail clearly
- **Clipboard/paste reliability**: isolate per-OS logic and retry once on transient errors
- **DB corruption risk**: use WAL mode, transactional writes, and backups on migration

---

## 10. Delivery sequence (recommended)
1. Schema + repos + defaults
2. Runtime action routing (F8/F7) + active note behavior
3. Notes CLI (including edit/delete/enter)
4. Modes + keybind CLI
5. Autopaste keybind + CLI
6. Tests, docs, polish

---

## 11. Documentation updates required
- Update `README.md` with:
  - setup/migration behavior
  - complete CLI command reference
  - keybind defaults and customization
  - active note semantics
  - autopaste behavior and caveats

End of plan.
