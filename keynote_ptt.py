import argparse
import base64
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

class OverlayManager:
    def __init__(self):
        self.msg_queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.root = tk.Tk()
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 0.85)
            self.root.configure(bg="#1a1a1a")

            self.label = tk.Label(
                self.root, 
                text="", 
                fg="#ffffff", 
                bg="#1a1a1a", 
                font=("Segoe UI", 11, "bold"),
                padx=15,
                pady=10
            )
            self.label.pack()

            self.root.withdraw()
            self._check_queue()
            self.root.mainloop()
        except Exception as e:
            print(f"[OVERLAY ERROR] Failed to initialize GUI overlay: {e}")

    def _check_queue(self):
        try:
            while True:
                msg, duration = self.msg_queue.get_nowait()
                self._show_message(msg, duration)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)

    def _show_message(self, text, duration):
        self.label.config(text=text)
        self.root.update_idletasks()
        
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        
        x = screen_w - w - 30
        y = screen_h - h - 70
        
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()
        
        if hasattr(self, '_hide_job') and self._hide_job:
            self.root.after_cancel(self._hide_job)
        self._hide_job = self.root.after(int(duration * 1000), self.root.withdraw)

    def show(self, text, duration=2.0):
        self.msg_queue.put((text, duration))

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
        overlay.show(f"Mode: {mode}")


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

    # Register hotkeys from database
    binds = hotkeys_service.get_keybinds()
    
    # Defaults and user binds setup
    for action, combo in binds.items():
        print(f"[BIND] {action}: {combo}")
        if action == "record_new_note":
            keyboard.on_press_key(combo, lambda _, a="record_new_note": app.start_recording(a), suppress=False)
            keyboard.on_release_key(combo, lambda _: app.stop_recording(), suppress=False)
        elif action == "record_append_latest":
            keyboard.on_press_key(combo, lambda _, a="record_append_latest": app.start_recording(a), suppress=False)
            keyboard.on_release_key(combo, lambda _: app.stop_recording(), suppress=False)
        elif action == "toggle_autopaste":
            keyboard.add_hotkey(combo, _toggle_autopaste)
        elif action.startswith("mode:"):
            mode_name = action.split("mode:")[1]
            keyboard.add_hotkey(combo, lambda m=mode_name: app.set_mode(m))

    print("Recording contexts active. Modifiers based on DB configuration.")
    print("Press Alt+F1 to quit.")

    keyboard.wait("alt+f1")
    print("Exiting...")
    time.sleep(0.1)


if __name__ == "__main__":
    main()
