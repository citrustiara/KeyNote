import typer
from pathlib import Path
from typing import Optional, List
import notes_service
import modes_service
import settings_service
import hotkeys

app = typer.Typer(help="KeyNote CLI")

note_app = typer.Typer(help="Manage notes")
app.add_typer(note_app, name="note")

mode_app = typer.Typer(help="Manage modes")
app.add_typer(mode_app, name="mode")

keybind_app = typer.Typer(help="Manage keybinds")
app.add_typer(keybind_app, name="keybind")

settings_app = typer.Typer(help="Manage settings")
app.add_typer(settings_app, name="settings")

autopaste_app = typer.Typer(help="Manage autopaste behavior")
app.add_typer(autopaste_app, name="autopaste")


@note_app.command("add")
def note_add(text: str, name: Optional[str] = None, mode: Optional[str] = None):
    mode_id = None
    if mode:
        m = modes_service.get_mode(mode)
        if m:
            mode_id = m["id"]
        else:
            typer.echo(f"Mode {mode} not found, ignoring.")
    nid = notes_service.create_note(text, name, mode_id)
    typer.echo(f"Added note {nid}")

@note_app.command("list")
def note_list(limit: int = 20, mode: Optional[str] = None, query: Optional[str] = None):
    # For now, simple list
    notes = notes_service.list_notes(limit)
    for n in notes:
        typer.echo(f"[{n['id']}] {n['name'] or 'Unnamed'}: {n['content'][:50]}...")

@note_app.command("show")
def note_show(id: Optional[int] = typer.Option(None, "--id"), name: Optional[str] = typer.Option(None, "--name")):
    if id:
        n = notes_service.get_note(id)
        if n:
            typer.echo(f"ID: {n['id']}\nName: {n['name']}\nContent: {n['content']}")
        else:
            typer.echo("Not found")
    elif name:
        ns = notes_service.get_note_by_name(name)
        for n in ns:
            typer.echo(f"ID: {n['id']}\nName: {n['name']}\nContent: {n['content']}\n---")
    else:
        typer.echo("Provide --id or --name")

@note_app.command("edit")
def note_edit(text: str, id: Optional[int] = typer.Option(None, "--id"), name: Optional[str] = typer.Option(None, "--name")):
    if id:
        notes_service.edit_note_content(id, text)
        typer.echo(f"Edited {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            notes_service.edit_note_content(ns[0]["id"], text)
            typer.echo(f"Edited {ns[0]['id']}")
        else:
            typer.echo(f"Found {len(ns)} notes with name {name}, please use --id.")

@note_app.command("rename")
def note_rename(id: int = typer.Option(..., "--id"), name: str = typer.Option(..., "--name")):
    notes_service.rename_note(id, name)
    typer.echo(f"Renamed {id} to {name}")

@note_app.command("append")
def note_append(text: str, id: Optional[int] = typer.Option(None, "--id"), name: Optional[str] = typer.Option(None, "--name")):
    if id:
        notes_service.append_to_note(id, text)
        typer.echo(f"Appended to {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            notes_service.append_to_note(ns[0]["id"], text)
            typer.echo(f"Appended to {ns[0]['id']}")
        else:
            typer.echo(f"Found {len(ns)} notes, use --id.")

@note_app.command("delete")
def note_delete(id: Optional[int] = typer.Option(None, "--id"), name: Optional[str] = typer.Option(None, "--name"), all: bool = False, yes: bool = False):
    if id:
        notes_service.delete_note_by_id(id)
        typer.echo(f"Deleted {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) > 1 and not all:
            typer.echo(f"Found {len(ns)} notes cleanly, use --all or --id.")
        else:
            notes_service.delete_notes_by_name(name)
            typer.echo(f"Deleted notes named {name}")

@note_app.command("enter")
def note_enter(id: Optional[int] = typer.Option(None, "--id"), name: Optional[str] = typer.Option(None, "--name")):
    if id:
        settings_service.set_active_note_id(id)
        typer.echo(f"Entered note {id}")
    elif name:
        ns = notes_service.get_note_by_name(name)
        if len(ns) == 1:
            settings_service.set_active_note_id(ns[0]["id"])
            typer.echo(f"Entered note {ns[0]['id']}")
        else:
            typer.echo(f"Found {len(ns)} notes, use --id.")

@note_app.command("current")
def note_current():
    nid = settings_service.get_active_note_id()
    if nid:
        typer.echo(f"Current note ID: {nid}")
    else:
        typer.echo("No active note.")

@note_app.command("leave")
def note_leave():
    settings_service.set_active_note_id(None)
    typer.echo("Left active note.")


@mode_app.command("list")
def mode_list():
    modes = modes_service.list_modes()
    for m in modes:
        typer.echo(f"{m['id']}: {m['name']} - {m['system_prompt'][:30]}...")

@mode_app.command("add")
def mode_add(name: str, prompt: Optional[str] = typer.Option(None, "--prompt"), prompt_file: Optional[Path] = typer.Option(None, "--prompt-file")):
    if prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt:
        typer.echo("Provide --prompt or --prompt-file")
        raise typer.Exit(1)
    modes_service.add_mode(name, prompt)
    typer.echo(f"Added mode {name}")

@mode_app.command("set-prompt")
def mode_set_prompt(name: str, prompt: Optional[str] = typer.Option(None, "--prompt"), prompt_file: Optional[Path] = typer.Option(None, "--prompt-file")):
    if prompt_file:
        prompt = prompt_file.read_text(encoding="utf-8")
    if not prompt:
        typer.echo("Provide --prompt or --prompt-file")
        raise typer.Exit(1)
    modes_service.set_mode_prompt(name, prompt)
    typer.echo(f"Updated mode {name}")

@mode_app.command("use")
def mode_use(name: str):
    settings_service.set_active_mode(name)
    typer.echo(f"Using mode {name}")

@mode_app.command("delete")
def mode_delete(name: str):
    modes_service.delete_mode(name)
    typer.echo(f"Deleted mode {name}")

@mode_app.command("bind")
def mode_bind(name: str, key: str = typer.Option(..., "--key")):
    hotkeys.set_keybind(f"mode:{name}", key)
    typer.echo(f"Bound mode {name} to {key}")


@keybind_app.command("list")
def keybind_list():
    binds = hotkeys.get_keybinds()
    for act, key in binds.items():
        typer.echo(f"{act}: {key}")

@keybind_app.command("set")
def keybind_set(action: str, key: str):
    hotkeys.set_keybind(action, key)
    typer.echo(f"Set {action} to {key}")

@keybind_app.command("clear")
def keybind_clear(action: str):
    hotkeys.clear_keybind(action)
    typer.echo(f"Cleared {action}")


@settings_app.command("get")
def settings_get(key: str):
    val = settings_service.get_setting(key)
    typer.echo(f"{key} = {val}")

@settings_app.command("set")
def settings_set_cmd(key: str, value: str):
    settings_service.set_setting(key, value)
    typer.echo(f"Set {key} = {value}")


@autopaste_app.command("on")
def autopaste_on():
    settings_service.set_autopaste_enabled(True)
    typer.echo("Autopaste ON")

@autopaste_app.command("off")
def autopaste_off():
    settings_service.set_autopaste_enabled(False)
    typer.echo("Autopaste OFF")

@autopaste_app.command("toggle")
def autopaste_toggle():
    val = not settings_service.is_autopaste_enabled()
    settings_service.set_autopaste_enabled(val)
    typer.echo(f"Autopaste toggled to {val}")

@autopaste_app.command("status")
def autopaste_status():
    val = settings_service.is_autopaste_enabled()
    typer.echo(f"Autopaste is {'ON' if val else 'OFF'}")

if __name__ == "__main__":
    app()
