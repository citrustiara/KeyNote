import argparse
import base64
import io
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import keyboard
import numpy as np
import pyperclip
import sounddevice as sd
import soundfile as sf


DEFAULT_PROMPTS = {
    "slack": Path("prompts/slack.txt"),
    "email": Path("prompts/email.txt"),
    "requirements": Path("prompts/requirements.txt"),
    "none": Path("prompts/none.txt"),
    "notes": Path("prompts/notes.txt"),
    "translate": Path("prompts/translate.txt"),
}


@dataclass
class AppConfig:
    server_url: str
    prompt_dir: Path
    hold_key: str = "f8"
    sample_rate: int = 16000
    channels: int = 1
    max_tokens: int = 512
    temperature: float = 0.2
    mode: str = "slack"


class PushToTalkFormatter:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._recording = False
        self._processing = False
        self._stream: Optional[sd.InputStream] = None
        self._frames: queue.Queue[np.ndarray] = queue.Queue()
        self._lock = threading.Lock()

    def set_mode(self, mode: str) -> None:
        if mode not in DEFAULT_PROMPTS:
            print(f"[WARN] Unknown mode '{mode}'. Available: {', '.join(DEFAULT_PROMPTS)}")
            return
        if self.cfg.mode == mode:
            return
        self.cfg.mode = mode
        print(f"[MODE] Switched to: {mode}")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[AUDIO] {status}")
        self._frames.put(indata.copy())

    def start_recording(self) -> None:
        with self._lock:
            if self._recording or self._processing:
                return
            self._recording = True

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

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        print("[REC] Recording stopped. Processing audio via server...")
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _collect_audio(self) -> Optional[np.ndarray]:
        chunks = []
        while not self._frames.empty():
            chunks.append(self._frames.get_nowait())
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0)

    def _prompt_content(self) -> str:
        rel = DEFAULT_PROMPTS[self.cfg.mode]
        path = self.cfg.prompt_dir / rel.name
        if not path.exists():
            return "Format the provided audio."
        return path.read_text(encoding="utf-8").strip()

    def _process_audio(self) -> None:
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
            print("\a", end="")
        except Exception as exc:
            print(f"[ERROR] {exc}")
        finally:
            with self._lock:
                self._processing = False


def parse_args() -> AppConfig:
    parser = argparse.ArgumentParser(description="Push-to-talk audio formatter using llama-server")
    parser.add_argument("--server-url", default="http://localhost:8080", help="URL of the running llama-server")
    parser.add_argument("--prompt-dir", default="prompts", help="Directory containing mode prompt files")
    parser.add_argument("--hold-key", default="f8", help="Hold this key to record (default: f8)")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--mode", choices=list(DEFAULT_PROMPTS.keys()), default="slack")
    args = parser.parse_args()

    return AppConfig(
        server_url=args.server_url,
        prompt_dir=Path(args.prompt_dir),
        hold_key=args.hold_key,
        sample_rate=args.sample_rate,
        channels=args.channels,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        mode=args.mode,
    )


def main() -> None:
    cfg = parse_args()
    app = PushToTalkFormatter(cfg)

    print("=== KeyNote Push-to-Talk Formatter (Server Mode) ===")
    print(f"Server: {cfg.server_url}")
    print(f"Hold [{cfg.hold_key}] to record. Release to process and format.")
    print("Mode hotkeys: 1=slack, 2=email, 3=req, 4=none, 5=notes, 6=translate (Ctrl+Alt+Num)")
    print("Press Alt+ESC to quit.")

    keyboard.on_press_key(cfg.hold_key, lambda _: app.start_recording(), suppress=False)
    keyboard.on_release_key(cfg.hold_key, lambda _: app.stop_recording(), suppress=False)

    keyboard.add_hotkey("ctrl+alt+1", lambda: app.set_mode("slack"))
    keyboard.add_hotkey("ctrl+alt+2", lambda: app.set_mode("email"))
    keyboard.add_hotkey("ctrl+alt+3", lambda: app.set_mode("requirements"))
    keyboard.add_hotkey("ctrl+alt+4", lambda: app.set_mode("none"))
    keyboard.add_hotkey("ctrl+alt+5", lambda: app.set_mode("notes"))
    keyboard.add_hotkey("ctrl+alt+6", lambda: app.set_mode("translate"))

    keyboard.wait("alt+esc")
    print("Exiting...")
    time.sleep(0.1)


if __name__ == "__main__":
    main()
