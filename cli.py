import click
from pathlib import Path
from typing import Optional
import sys
import subprocess
import notes_service
import modes_service
import settings_service
import hotkeys
import export_service

@click.group(help="KeyNote CLI")
def app():
    pass

@click.group(help="Manage notes")
def note_group():
    pass

@click.group(help="Manage modes")
def mode_group():
    pass

@click.group(help="Manage keybinds")
def keybind_group():
    pass

@click.group(help="Manage settings")
def settings_group():
    pass

@click.group(help="Manage autopaste behavior")
def autopaste_group():
    pass

@click.group(help="Manage audio input devices")
def audio_group():
    pass

app.add_command(note_group, name="note")
app.add_command(mode_group, name="mode")
app.add_command(keybind_group, name="keybind")
app.add_command(settings_group, name="settings")
app.add_command(autopaste_group, name="autopaste")
app.add_command(audio_group, name="audio")


# ── Note commands ────────────────────────────────────────────────────────────

@note_group.command("add")
@click.argument("text")
@click.option("--name", default=None)
@click.option("--mode", default=None)
def note_add(text, name, mode):
    mode_id = None
    if mode:
        m = modes_service.get_mode(mode)
        if m:
            mode_id = m["id"]
        else:
            click.echo(f"Mode {mode} not found, ignoring.")
    nid = notes_service.create_note(text, name, mode_id)
    click.echo(f"Added note {nid}")


@note_group.command("list")
@click.option("--limit", "-l", default=20, type=int, help="Limit number of notes")
@click.option("--mode", "-m", default=None, help="Filter by mode")
@click.option("--query", "-q", default=None, help="Search by name/content/ID")
def note_list(limit, mode, query):
    """List notes. Use --query to search by name/content/ID, --mode to filter by mode."""
    if query or mode:
        notes = notes_service.search_notes(query=query, mode=mode, limit=limit)
    else:
        notes = notes_service.list_notes(limit)
    if not notes:
        click.echo("No notes found.")
        return
    for n in notes:
        mode_name = n.get("mode_name") or "—"
        name = n["name"] or "Unnamed"
        click.echo(f"[{n['id']}] {name} ({mode_name}): {n['content'][:50]}...")


@note_group.command("search")
@click.argument("query")
@click.option("--mode", "-m", default=None)
@click.option("--limit", "-l", default=50, type=int)
def note_search(query, mode, limit):
    """Search notes by name, content, or ID."""
    notes = notes_service.search_notes(query=query, mode=mode, limit=limit)
    if not notes:
        click.echo("No notes found.")
        return
    for n in notes:
        mode_name = n.get("mode_name") or "—"
        name = n["name"] or "Unnamed"
        click.echo(f"[{n['id']}] {name} ({mode_name}): {n['content'][:50]}...")


@note_group.command("show")
@click.option("--id", type=int)
@click.option("--name")
def note_show(id, name):
    if id:
        n = notes_service.get_note(id)
        if n:
            mode_name = n.get("mode_name") or "—"
            click.echo(f"ID: {n['id']}\nName: {n['name']}\nMode: {mode_name}\nContent:\n{n['content']}")
        else:
            click.echo("Not found")
    elif name:
        ns = notes_service.get_note_by_name(name)
        for n in ns:
            mode_name = n.get("mode_name") or "—"
            click.echo(f"ID: {n['id']}\nName: {n['name']}\nMode: {mode_name}\nContent:\n{n['content']}\n---")
    else:
        click.echo("Provide --id or --name")


@note_group.command("edit")
@click.argument("text")
@click.option("--id", type=int)
@click.option("--name")
def note_edit(text, id, name):
    if id:
        notes_service.edit_note_content(id, text)
        click.echo(f"Edited {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            notes_service.edit_note_content(ns[0]["id"], text)
            click.echo(f"Edited {ns[0]['id']}")
        else:
            click.echo(f"Found {len(ns)} notes with name {name}, please use --id.")


@note_group.command("rename")
@click.option("--id", required=True, type=int)
@click.option("--name", required=True)
def note_rename(id, name):
    notes_service.rename_note(id, name)
    click.echo(f"Renamed {id} to {name}")


@note_group.command("append")
@click.argument("text")
@click.option("--id", type=int)
@click.option("--name")
def note_append(text, id, name):
    if id:
        notes_service.append_to_note(id, text)
        click.echo(f"Appended to {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            notes_service.append_to_note(ns[0]["id"], text)
            click.echo(f"Appended to {ns[0]['id']}")
        else:
            click.echo(f"Found {len(ns)} notes, use --id.")


@note_group.command("delete")
@click.option("--id", type=int)
@click.option("--name")
@click.option("--all", is_flag=True, default=False)
@click.option("--yes", "-y", is_flag=True, default=False)
def note_delete(id, name, all, yes):
    if id:
        notes_service.delete_note_by_id(id)
        click.echo(f"Deleted {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) > 1 and not all:
            click.echo(f"Found {len(ns)} notes, use --all or --id.")
        else:
            notes_service.delete_notes_by_name(name)
            click.echo(f"Deleted notes named {name}")


@note_group.command("enter")
@click.option("--id", type=int)
@click.option("--name")
def note_enter(id, name):
    if id:
        settings_service.set_active_note_id(id)
        click.echo(f"Entered note {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            settings_service.set_active_note_id(ns[0]["id"])
            click.echo(f"Entered note {ns[0]['id']}")
        else:
            click.echo(f"Found {len(ns)} notes, use --id.")


@note_group.command("current")
def note_current():
    nid = settings_service.get_active_note_id()
    if nid:
        click.echo(f"Current note ID: {nid}")
    else:
        click.echo("No active note.")


@note_group.command("leave")
def note_leave():
    settings_service.set_active_note_id(None)
    click.echo("Left active note.")


@note_group.command("export")
@click.option("--id", type=int, help="Export a single note by ID")
@click.option("--all", "-a", is_flag=True, default=False, help="Export all notes")
@click.option("--clipboard", "-c", is_flag=True, default=False, help="Copy single note content to clipboard")
@click.option("--format", "-f", default="json", help="Export format: json, md, txt")
@click.option("--output", "-o", help="Output file path")
def note_export(id, all, clipboard, format, output):
    """Export notes to a file or clipboard."""
    if not id and not all:
        click.echo("Provide --id <id> or --all")
        sys.exit(1)

    if clipboard:
        if all:
            click.echo("--clipboard only works with --id (single note)")
            sys.exit(1)
        if not id:
            click.echo("--clipboard requires --id")
            sys.exit(1)
        ok = export_service.export_note_to_clipboard(id)
        if ok:
            click.echo(f"Note {id} copied to clipboard.")
        else:
            click.echo(f"Note {id} not found.")
            sys.exit(1)
        return

    try:
        note_ids = [id] if id and not all else None
        path = export_service.export_notes_to_file(note_ids, format, output)
        click.echo(f"Exported to {path}")
    except (ValueError, FileExistsError) as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


# ── Mode commands ────────────────────────────────────────────────────────────

@mode_group.command("list")
def mode_list():
    modes = modes_service.list_modes()
    active = settings_service.get_active_mode()
    for m in modes:
        marker = ">>" if m["name"] == active else "  "
        click.echo(f"{marker} {m['id']}: {m['name']} - {m['system_prompt'][:30]}...")


@mode_group.command("add")
@click.argument("name")
@click.option("--prompt")
@click.option("--prompt-file", type=click.Path(exists=True, path_type=Path))
def mode_add(name, prompt, prompt_file):
    if prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt:
        click.echo("Provide --prompt or --prompt-file")
        sys.exit(1)
    modes_service.add_mode(name, prompt)
    click.echo(f"Added mode {name}")


@mode_group.command("set-prompt")
@click.argument("name")
@click.option("--prompt")
@click.option("--prompt-file", type=click.Path(exists=True, path_type=Path))
def mode_set_prompt(name, prompt, prompt_file):
    if prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt:
        click.echo("Provide --prompt or --prompt-file")
        sys.exit(1)
    modes_service.set_mode_prompt(name, prompt)
    click.echo(f"Updated mode {name}")


@mode_group.command("use")
@click.argument("name")
def mode_use(name):
    settings_service.set_active_mode(name)
    click.echo(f"Using mode {name}")


@mode_group.command("delete")
@click.argument("name")
def mode_delete(name):
    modes_service.delete_mode(name)
    click.echo(f"Deleted mode {name}")


@mode_group.command("bind")
@click.argument("name")
@click.option("--key", required=True)
def mode_bind(name, key):
    hotkeys.set_keybind(f"mode:{name}", key)
    click.echo(f"Bound mode {name} to {key}")


@mode_group.command("sync")
def mode_sync():
    modes_service.sync_workflows()
    click.echo("Workflows synced successfully between files and DB.")


# ── Keybind commands ─────────────────────────────────────────────────────────

@keybind_group.command("list")
def keybind_list():
    binds = hotkeys.get_keybinds()
    for act, key in binds.items():
        click.echo(f"{act}: {key}")


@keybind_group.command("set")
@click.argument("action")
@click.argument("key")
def keybind_set(action, key):
    """Set a keybind. Valid actions include:
    record_new_note, record_append_latest, toggle_long_recording, toggle_autopaste,
    mode_prev, mode_next, mode:<name>"""
    hotkeys.set_keybind(action, key)
    click.echo(f"Set {action} to {key}")


@keybind_group.command("clear")
@click.argument("action")
def keybind_clear(action):
    hotkeys.clear_keybind(action)
    click.echo(f"Cleared {action}")


# ── Settings commands ────────────────────────────────────────────────────────

@settings_group.command("get")
@click.argument("key")
def settings_get(key):
    val = settings_service.get_setting(key)
    click.echo(f"{key} = {val}")


@settings_group.command("set")
@click.argument("key")
@click.argument("value")
def settings_set_cmd(key, value):
    settings_service.set_setting(key, value)
    click.echo(f"Set {key} = {value}")


# ── Audio commands ───────────────────────────────────────────────────────────

def _device_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _print_audio_status():
    primary = settings_service.get_setting("audio_input_device") or "default input"
    secondary = settings_service.get_setting("audio_secondary_input_device")
    if secondary:
        click.echo(f"Audio input: {primary} + {secondary}")
    else:
        click.echo(f"Audio input: {primary}")


@audio_group.command("list")
@click.option("--all", "show_all", is_flag=True, default=False, help="Show output-only devices too.")
def audio_list(show_all):
    """List PortAudio devices that KeyNote can select."""
    import sounddevice as sd

    hostapis = sd.query_hostapis()
    devices = sd.query_devices()
    for index, device in enumerate(devices):
        if not show_all and device["max_input_channels"] <= 0:
            continue
        hostapi = hostapis[device["hostapi"]]["name"]
        marker = "input" if device["max_input_channels"] > 0 else "output"
        click.echo(
            f"{index}: {device['name']} [{hostapi}] "
            f"{marker}, in={device['max_input_channels']}, out={device['max_output_channels']}, "
            f"default_sr={int(device['default_samplerate'])}"
        )

    click.echo(
        "\nFor PC audio on Windows, select an input-style loopback device such as "
        "'Stereo Mix', 'What U Hear', or a WASAPI loopback device if your system exposes one."
    )


@audio_group.command("set")
@click.option("--primary", help="Primary input device index or exact/partial name.")
@click.option("--secondary", help="Optional second input device to mix with the primary.")
@click.option("--clear-primary", is_flag=True, default=False)
@click.option("--clear-secondary", is_flag=True, default=False)
def audio_set(primary, secondary, clear_primary, clear_secondary):
    """Persist input devices used by keynote start."""
    primary = _device_value(primary)
    secondary = _device_value(secondary)

    if clear_primary:
        settings_service.clear_setting("audio_input_device")
        click.echo("Cleared primary audio input; default input will be used.")
    elif primary is not None:
        settings_service.set_setting("audio_input_device", primary)
        click.echo(f"Primary audio input set to {primary}")

    if clear_secondary:
        settings_service.clear_setting("audio_secondary_input_device")
        click.echo("Cleared secondary audio input.")
    elif secondary is not None:
        settings_service.set_setting("audio_secondary_input_device", secondary)
        click.echo(f"Secondary audio input set to {secondary}")

    if primary is None and secondary is None and not clear_primary and not clear_secondary:
        _print_audio_status()


@audio_group.command("status")
def audio_status():
    _print_audio_status()


# ── Autopaste commands ───────────────────────────────────────────────────────

@autopaste_group.command("on")
def autopaste_on():
    settings_service.set_autopaste_enabled(True)
    click.echo("Autopaste ON")


@autopaste_group.command("off")
def autopaste_off():
    settings_service.set_autopaste_enabled(False)
    click.echo("Autopaste OFF")


@autopaste_group.command("toggle")
def autopaste_toggle():
    val = not settings_service.is_autopaste_enabled()
    settings_service.set_autopaste_enabled(val)
    click.echo(f"Autopaste toggled to {val}")


@autopaste_group.command("status")
def autopaste_status():
    val = settings_service.is_autopaste_enabled()
    click.echo(f"Autopaste is {'ON' if val else 'OFF'}")


# ── TUI command ──────────────────────────────────────────────────────────────

@app.command("tui")
def tui():
    """Launch the interactive Terminal User Interface."""
    try:
        from tui.app import KeyNoteApp
        app_instance = KeyNoteApp()
        app_instance.run()
    except ImportError as e:
        click.echo(f"TUI dependencies not installed: {e}")
        click.echo("Run: uv add textual")
@app.command("start")
@click.option("--server-url", default="http://localhost:8080", help="llama-server URL")
@click.option("--input-device", default=None, help="Primary sounddevice input device index or name.")
@click.option("--secondary-input-device", default=None, help="Optional second input device mixed into recordings.")
@click.option("--transcript-segment-min-sec", default=2.5, type=float, help="Shortest transcript segment before a quiet split.")
@click.option("--transcript-segment-target-sec", default=5.0, type=float, help="Preferred transcript segment length.")
@click.option("--transcript-segment-max-sec", default=8.0, type=float, help="Longest transcript segment before forcing a split.")
@click.option("--transcript-silence-sec", default=0.35, type=float, help="Quiet duration that marks a word boundary.")
@click.option("--transcript-silence-rms", default=0.010, type=float, help="Absolute RMS floor for silence detection.")
@click.option("--transcript-speech-rms", default=0.018, type=float, help="RMS level treated as speech.")
@click.option("--long-segment-min-sec", default=1.5, type=float, help="Shortest long-recording segment before a quiet split.")
@click.option("--long-segment-max-sec", default=30.0, type=float, help="Hard split length for long recordings.")
def start(
    server_url,
    input_device,
    secondary_input_device,
    transcript_segment_min_sec,
    transcript_segment_target_sec,
    transcript_segment_max_sec,
    transcript_silence_sec,
    transcript_silence_rms,
    transcript_speech_rms,
    long_segment_min_sec,
    long_segment_max_sec,
):
    """Start the Push-to-Talk background service."""
    script_path = Path(__file__).parent / "keynote_ptt.py"
    cmd = [
        sys.executable,
        str(script_path),
        "--server-url",
        server_url,
    ]
    if input_device is not None:
        cmd.extend(["--input-device", input_device])
    if secondary_input_device is not None:
        cmd.extend(["--secondary-input-device", secondary_input_device])
    cmd.extend([
        "--transcript-segment-min-sec",
        str(transcript_segment_min_sec),
        "--transcript-segment-target-sec",
        str(transcript_segment_target_sec),
        "--transcript-segment-max-sec",
        str(transcript_segment_max_sec),
        "--transcript-silence-sec",
        str(transcript_silence_sec),
        "--transcript-silence-rms",
        str(transcript_silence_rms),
        "--transcript-speech-rms",
        str(transcript_speech_rms),
        "--long-segment-min-sec",
        str(long_segment_min_sec),
        "--long-segment-max-sec",
        str(long_segment_max_sec),
    ])
    click.echo(f"Starting KeyNote PTT service: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        click.echo("\nStopping KeyNote PTT service.")
    except Exception as e:
        click.echo(f"Error starting service: {e}")
        sys.exit(1)


@app.command("launch-server")
@click.option(
    "--script",
    "script_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Override the bundled llama-server launch script.",
)
def launch_server(script_path):
    """Launch the bundled E4B llama-server configuration."""
    scripts_dir = Path(__file__).parent / "scripts"
    if script_path is None:
        script_path = scripts_dir / (
            "launch_server_e4b.ps1" if sys.platform.startswith("win") else "launch_server_e4b.sh"
        )

    if not script_path.exists():
        click.echo(f"Launch script not found: {script_path}")
        sys.exit(1)

    if script_path.suffix.lower() == ".ps1":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
    else:
        cmd = ["bash", str(script_path)]

    click.echo(f"Launching llama-server: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        click.echo("\nStopping llama-server.")
    except Exception as e:
        click.echo(f"Error launching llama-server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
