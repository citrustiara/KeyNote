import argparse
import base64
import ctypes
import ctypes.wintypes
import io
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import keyboard
import numpy as np
import pyperclip
import sounddevice as sd
import soundfile as sf

import modes_service
import notes_service
import settings_service
import hotkeys as hotkeys_service
import autopaste


import tkinter as tk


def _work_area(root):
    """Return usable screen bounds on Windows, with a portable Tk fallback."""
    if not hasattr(ctypes, "windll"):
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

    rect = ctypes.wintypes.RECT()
    if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class OverlayManager:
    """Compact overlay with transient mode picker and notifications."""

    def __init__(self):
        self.msg_queue = queue.Queue()
        self._hide_job = None
        self._notification_active = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.80)
            self.root.configure(bg="#1a1a1a")

            # Container frame
            self.frame = tk.Frame(self.root, bg="#1a1a1a")
            self.frame.pack(padx=6, pady=3)

            # Transient notification label (above mode bar)
            self.notification_label = tk.Label(
                self.frame,
                text="",
                fg="#ffffff",
                bg="#1a1a1a",
                font=("Consolas", 8, "bold"),
                anchor="w",
            )
            self.notification_label.pack(fill="x")

            # Mode picker: previous, active, next.
            self.mode_frame = tk.Frame(self.frame, bg="#1a1a1a")
            self.mode_frame.pack(fill="x")

            self.prev_mode_label = tk.Label(
                self.mode_frame,
                text="",
                fg="#8a8a8a",
                bg="#1a1a1a",
                font=("Consolas", 8),
                anchor="w",
            )
            self.prev_mode_label.pack(fill="x")

            self.mode_label = tk.Label(
                self.mode_frame,
                text="> (no mode)",
                fg="#4fc3f7",
                bg="#1a1a1a",
                font=("Consolas", 8, "bold"),
                anchor="w",
            )
            self.mode_label.pack(fill="x")

            self.next_mode_label = tk.Label(
                self.mode_frame,
                text="",
                fg="#8a8a8a",
                bg="#1a1a1a",
                font=("Consolas", 8),
                anchor="w",
            )
            self.next_mode_label.pack(fill="x")

            self._position()
            self.root.deiconify()
            self._bring_to_front()
            self._hide_notification()
            self._schedule_hide(5.0)

            self._check_queue()
            self.root.mainloop()
        except Exception as e:
            print(f"[OVERLAY ERROR] Failed to initialize GUI overlay: {e}")

    def _position(self):
        """Position overlay at bottom-right corner."""
        self.root.update_idletasks()
        left, top, right, bottom = _work_area(self.root)
        w = max(self.root.winfo_reqwidth(), self.root.winfo_width(), 1)
        h = max(self.root.winfo_reqheight(), self.root.winfo_height(), 1)
        x = max(left + 10, right - w - 16)
        y = max(top + 10, bottom - h - 16)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _bring_to_front(self, repeat=3):
        self.root.lift()
        self.root.attributes("-topmost", False)
        self.root.attributes("-topmost", True)
        if repeat > 0:
            self.root.after(500, lambda: self._bring_to_front(repeat - 1))

    def _show_overlay(self):
        self.root.deiconify()
        self._position()
        self._bring_to_front()

    def _schedule_hide(self, delay):
        if self._hide_job:
            try:
                self.root.after_cancel(self._hide_job)
            except tk.TclError:
                pass
        self._hide_job = self.root.after(int(delay * 1000), self._hide_overlay)

    def _hide_overlay(self):
        self._hide_job = None
        if self._notification_active:
            self._schedule_hide(1.0)
            return
        self.root.withdraw()

    def _show_notification(self, text, duration):
        self._notification_active = True
        self.notification_label.config(text=text)
        self.notification_label.pack(fill="x", before=self.mode_frame)
        self.root.update_idletasks()
        self._show_overlay()
        self.root.after(int(duration * 1000), self._hide_notification)

    def _hide_notification(self):
        self._notification_active = False
        self.notification_label.config(text="")
        self.notification_label.pack_forget()
        self.root.update_idletasks()
        self._position()
        self._schedule_hide(5.0)

    def update_mode_display(self, mode_name: str):
        """Update the persistent mode bar. Safe to call from any thread."""
        self.msg_queue.put((f"__mode__:{mode_name}", 0))

    def show(self, text, duration=2.0):
        """Show a transient notification message."""
        self.msg_queue.put((text, duration))

    def _process_queue_message(self, text, duration):
        if text.startswith("__mode__:"):
            mode_name = text[len("__mode__:"):]
            prev_mode, next_mode = self._neighbor_modes(mode_name)
            self.prev_mode_label.config(text=prev_mode)
            self.mode_label.config(text=f"> {mode_name}")
            self.next_mode_label.config(text=next_mode)
            self.root.update_idletasks()
            self._show_overlay()
            self._schedule_hide(5.0)
        else:
            self._show_notification(text, duration)

    def _neighbor_modes(self, mode_name: str):
        modes = modes_service.list_modes()
        names = [m["name"] for m in modes]
        if not names:
            return "", ""
        try:
            idx = names.index(mode_name)
        except ValueError:
            return "", ""
        return names[(idx - 1) % len(names)], names[(idx + 1) % len(names)]

    # Override _check_queue to route mode updates
    def _check_queue(self):
        try:
            while True:
                msg, duration = self.msg_queue.get_nowait()
                self._process_queue_message(msg, duration)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)

overlay = OverlayManager()


@dataclass
class AppConfig:
    server_url: str
    sample_rate: int = 16000
    channels: int = 1
    max_tokens: int = 512
    temperature: float = 0.2


class PushToTalkFormatter:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._recording = False
        self._processing = False
        self._stream: Optional[sd.InputStream] = None
        self._frames: queue.Queue[np.ndarray] = queue.Queue()
        self._lock = threading.Lock()

    def set_mode(self, mode: str) -> None:
        db_mode = modes_service.get_mode(mode)
        if not db_mode:
            print(f"[WARN] Unknown mode '{mode}'.")
            return
        
        current_mode = settings_service.get_active_mode()
        if current_mode == mode:
            return
        settings_service.set_active_mode(mode)
        print(f"[MODE] Switched to: {mode}")
        overlay.update_mode_display(mode)

    def cycle_mode(self, direction: int) -> None:
        new_mode = modes_service.cycle_mode(direction)
        print(f"[MODE] Switched to: {new_mode}")
        overlay.update_mode_display(new_mode)


    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[AUDIO] {status}")
        self._frames.put(indata.copy())

    def start_recording(self, context_action: str) -> None:
        with self._lock:
            if self._recording or self._processing:
                return
            self._recording = True
            self._recording_context = context_action

            while not self._frames.empty():
                self._frames.get_nowait()

            self._stream = sd.InputStream(
                samplerate=self.cfg.sample_rate,
                channels=self.cfg.channels,
                dtype="float32",
                callback=self._audio_callback,
                blocksize=0,
            )
            self._stream.start()
            print("[REC] Recording started...")

    def stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            self._processing = True
            context_action = getattr(self, "_recording_context", "new_note")

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        print("[REC] Recording stopped. Processing audio via server...")
        threading.Thread(target=self._process_audio, args=(context_action,), daemon=True).start()

    def _collect_audio(self) -> Optional[np.ndarray]:
        chunks = []
        while not self._frames.empty():
            chunks.append(self._frames.get_nowait())
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0)

    def _prompt_content(self) -> str:
        mode_name = settings_service.get_active_mode()
        db_mode = modes_service.get_mode(mode_name)
        if db_mode:
            return db_mode["system_prompt"]
        return "Format the provided audio."

    def _process_audio(self, context_action: str) -> None:
        try:
            audio = self._collect_audio()
            if audio is None or len(audio) == 0:
                print("[INFO] No audio captured.")
                return

            # Prepare audio data in memory
            buffer = io.BytesIO()
            sf.write(buffer, audio, self.cfg.sample_rate, format="wav")
            audio_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            prompt = self._prompt_content()

            # Prepare the request payload for llama-server
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "input_audio",
                                "input_audio": {"data": audio_b64, "format": "wav"}
                            }
                        ]
                    }
                ],
                "max_tokens": self.cfg.max_tokens,
                "temperature": self.cfg.temperature,
            }

            url = f"{self.cfg.server_url.rstrip('/')}/v1/chat/completions"
            
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            result = data["choices"][0]["message"]["content"].strip()
            if not result:
                print("[WARN] Server returned empty output.")
                return

            pyperclip.copy(result)
            print("[OK] Output copied to clipboard.")

            # Save to DB according to context_action
            if context_action == "record_new_note":
                mode_name = settings_service.get_active_mode()
                db_mode = modes_service.get_mode(mode_name)
                mode_id = db_mode["id"] if db_mode else None
                nid = notes_service.create_note(result, mode_id=mode_id)
                print(f"[DB] Created new note (ID: {nid}).")
                overlay.show(f"Saved: Note {nid}")
            elif context_action == "record_append_latest":
                active_nid = settings_service.get_active_note_id()
                if active_nid:
                    notes_service.append_to_note(active_nid, result)
                    print(f"[DB] Appended to active note (ID: {active_nid}).")
                    overlay.show(f"Appended to Note {active_nid}")
                else:
                    notes_service.append_to_latest_note(result)
                    print("[DB] Appended to latest note.")
                    overlay.show("Appended to latest Note")

            # Autopaste logic
            if settings_service.is_autopaste_enabled():
                autopaste.trigger_paste()
                print("[OK] Autopaste emitted.")

            print("\a", end="")
        except Exception as exc:
            print(f"[ERROR] {exc}")
        finally:
            with self._lock:
                self._processing = False


def parse_args() -> AppConfig:
    parser = argparse.ArgumentParser(description="Push-to-talk audio formatter using llama-server")
    parser.add_argument("--server-url", default="http://localhost:8080", help="URL of the running llama-server")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()

    return AppConfig(
        server_url=args.server_url,
        sample_rate=args.sample_rate,
        channels=args.channels,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

def _toggle_autopaste():
    val = not settings_service.is_autopaste_enabled()
    settings_service.set_autopaste_enabled(val)
    print(f"[CONFIG] Autopaste toggled to {'ON' if val else 'OFF'}")
    overlay.show(f"Autopaste: {'ON' if val else 'OFF'}")


def main() -> None:
    cfg = parse_args()
    app = PushToTalkFormatter(cfg)

    print("=== KeyNote Push-to-Talk Formatter (DB Server Mode) ===")
    print(f"Server: {cfg.server_url}")

    # Show current mode on startup
    current_mode = settings_service.get_active_mode()
    overlay.update_mode_display(current_mode)

    # Register hotkeys from database
    binds = hotkeys_service.get_keybinds()
    
    for action, combo in binds.items():
        if not combo:
            continue
        try:
            print(f"[BIND] {action}: {combo}")
            if action == "record_new_note":
                keyboard.on_press_key(combo, lambda _, a="record_new_note": app.start_recording(a), suppress=False)
                keyboard.on_release_key(combo, lambda _: app.stop_recording(), suppress=False)
            elif action == "record_append_latest":
                keyboard.on_press_key(combo, lambda _, a="record_append_latest": app.start_recording(a), suppress=False)
                keyboard.on_release_key(combo, lambda _: app.stop_recording(), suppress=False)
            elif action == "toggle_autopaste":
                keyboard.add_hotkey(combo, _toggle_autopaste)
            elif action == "mode_prev":
                keyboard.add_hotkey(combo, lambda: app.cycle_mode(-1))
            elif action == "mode_next":
                keyboard.add_hotkey(combo, lambda: app.cycle_mode(1))
            elif action.startswith("mode:"):
                mode_name = action.split("mode:")[1]
                keyboard.add_hotkey(combo, lambda m=mode_name: app.set_mode(m))
        except ValueError as e:
            print(f"[WARN] Failed to bind '{action}' to '{combo}': {e}")

    print("Recording contexts active. Modifiers based on DB configuration.")
    print("Press Alt+F1 to quit.")

    keyboard.wait("alt+f1")
    print("Exiting...")
    time.sleep(0.1)


if __name__ == "__main__":
    main()
