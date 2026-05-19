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


EMPTY_AUDIO_INSTRUCTION = (
    "It is acceptable to output nothing only if nothing was said."
)

BUILTIN_PROMPTS = {
    "transcript": (
        "You are a precise transcription assistant.\n\n"
        "Task:\n"
        "1) Transcribe the provided audio input into text.\n"
        "2) Ensure accuracy in spelling and punctuation.\n"
        "3) Do not add any summary or interpretation.\n"
        "4) It is acceptable to output nothing only if nothing was said.\n\n"
        "Return only the transcript."
    ),
    "translate": (
        "You are a professional translator.\n\n"
        "Task:\n"
        "1) Translate the provided Polish audio input into natural, fluent English.\n"
        "2) Maintain the original meaning, context, and tone.\n"
        "3) If there are specific industry terms, use their standard English equivalents.\n"
        "4) It is acceptable to output nothing only if nothing was said.\n\n"
        "Return only the English translation."
    ),
    "clean_transcript": (
        "You are a precise transcription and light editing assistant.\n\n"
        "Task:\n"
        "1) Transcribe the provided audio input into text.\n"
        "2) Remove filler words and false starts when they do not change the meaning.\n"
        "3) Lightly fix grammar and punctuation.\n"
        "4) Keep the wording very close to what was said. Make it sound only slightly nicer.\n"
        "5) Do not summarize or add interpretation.\n"
        "6) It is acceptable to output nothing only if nothing was said.\n\n"
        "Return only the cleaned transcript."
    ),
}


@dataclass
class AppConfig:
    server_url: str
    sample_rate: int = 16000
    channels: int = 1
    input_device: str | None = None
    secondary_input_device: str | None = None
    max_tokens: int = 512
    temperature: float = 0.2
    transcript_segment_min_sec: float = 2.5
    transcript_segment_target_sec: float = 5.0
    transcript_segment_max_sec: float = 8.0
    transcript_silence_sec: float = 0.35
    transcript_silence_rms: float = 0.010
    transcript_speech_rms: float = 0.018
    long_segment_min_sec: float = 1.5
    long_segment_max_sec: float = 30.0


@dataclass
class TranscriptSession:
    context_action: str
    mode_name: str
    mode_id: int | None
    note_id: int | None = None
    requested_mode_name: str | None = None
    copy_results: bool = True
    realtime_paste: bool = True
    use_previous_output: bool = False
    previous_output: str = ""
    note_separator: str = "\n"
    segment_min_sec: float = 2.5
    segment_target_sec: float = 5.0
    segment_max_sec: float = 8.0
    force_split_sec: float = 10.0


class PushToTalkFormatter:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._recording = False
        self._processing = False
        self._stream: Optional[sd.InputStream] = None
        self._streams: list[sd.InputStream] = []
        self._frames: queue.Queue[np.ndarray] = queue.Queue()
        self._source_frames: list[queue.Queue[np.ndarray]] = []
        self._mixer_thread: threading.Thread | None = None
        self._segment_queue: queue.Queue[tuple[int, np.ndarray] | None] = queue.Queue()
        self._recording_done = threading.Event()
        self._segment_index = 0
        self._current_session: TranscriptSession | None = None
        self._lock = threading.Lock()

    def set_mode(self, mode: str) -> None:
        db_mode = modes_service.get_mode(mode)
        if not db_mode and mode in BUILTIN_PROMPTS:
            modes_service.add_mode(mode, BUILTIN_PROMPTS[mode])
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
        self._frames.put(self._normalize_audio_chunk(indata.copy()))

    def _source_audio_callback(self, source_index: int):
        def callback(indata, frames, time_info, status):
            if status:
                print(f"[AUDIO:{source_index + 1}] {status}")
            self._source_frames[source_index].put(self._normalize_audio_chunk(indata.copy()))

        return callback

    def _normalize_audio_chunk(self, chunk: np.ndarray) -> np.ndarray:
        if chunk.ndim == 1:
            chunk = chunk.reshape(-1, 1)
        if chunk.shape[1] == self.cfg.channels:
            return chunk
        mono = np.mean(chunk, axis=1, keepdims=True)
        if self.cfg.channels == 1:
            return mono.astype(np.float32)
        return np.repeat(mono, self.cfg.channels, axis=1).astype(np.float32)

    def _mix_chunks(self, chunks: list[np.ndarray]) -> np.ndarray:
        if len(chunks) == 1:
            return chunks[0]
        max_len = max(len(chunk) for chunk in chunks)
        mixed = np.zeros((max_len, self.cfg.channels), dtype=np.float32)
        for chunk in chunks:
            if len(chunk) < max_len:
                padded = np.zeros((max_len, self.cfg.channels), dtype=np.float32)
                padded[:len(chunk)] = chunk
                chunk = padded
            mixed += chunk
        return np.clip(mixed / max(len(chunks), 1), -1.0, 1.0)

    def _mix_audio_sources(self) -> None:
        while not self._recording_done.is_set() or any(not q.empty() for q in self._source_frames):
            chunks = []
            for source_queue in self._source_frames:
                try:
                    chunks.append(source_queue.get_nowait())
                except queue.Empty:
                    pass

            if not chunks:
                time.sleep(0.02)
                continue

            time.sleep(0.015)
            for source_queue in self._source_frames:
                try:
                    chunks.append(source_queue.get_nowait())
                except queue.Empty:
                    pass

            self._frames.put(self._mix_chunks(chunks))

    def _configured_input_devices(self) -> list[str | int | None]:
        devices = [self._parse_device_identifier(self.cfg.input_device)]
        if self.cfg.secondary_input_device:
            devices.append(self._parse_device_identifier(self.cfg.secondary_input_device))
        return devices

    @staticmethod
    def _parse_device_identifier(device: str | None) -> str | int | None:
        if device is None:
            return None
        cleaned = device.strip()
        if not cleaned:
            return None
        if cleaned.lstrip("-").isdigit():
            return int(cleaned)
        return cleaned

    def _open_audio_streams(self) -> None:
        devices = self._configured_input_devices()
        blocksize = max(1, int(self.cfg.sample_rate * 0.1))
        self._streams = []
        self._source_frames = []

        try:
            if len(devices) == 1:
                self._stream = sd.InputStream(
                    samplerate=self.cfg.sample_rate,
                    channels=self.cfg.channels,
                    dtype="float32",
                    device=devices[0],
                    callback=self._audio_callback,
                    blocksize=blocksize,
                )
                self._stream.start()
                self._streams = [self._stream]
                return

            self._stream = None
            for index, device in enumerate(devices):
                self._source_frames.append(queue.Queue())
                stream = sd.InputStream(
                    samplerate=self.cfg.sample_rate,
                    channels=self.cfg.channels,
                    dtype="float32",
                    device=device,
                    callback=self._source_audio_callback(index),
                    blocksize=blocksize,
                )
                stream.start()
                self._streams.append(stream)

            self._mixer_thread = threading.Thread(target=self._mix_audio_sources, daemon=True)
            self._mixer_thread.start()
        except Exception:
            self._close_audio_streams()
            raise

    def _close_audio_streams(self) -> None:
        for stream in self._streams:
            stream.stop()
            stream.close()
        self._streams = []
        self._stream = None

    def _active_mode_info(self) -> tuple[str, int | None]:
        mode_name = settings_service.get_active_mode()
        db_mode = modes_service.get_mode(mode_name)
        return mode_name, db_mode["id"] if db_mode else None

    @staticmethod
    def _is_transcript_mode(mode_name: str) -> bool:
        return mode_name.lower() == "transcript"

    @staticmethod
    def _is_segmented_hold_mode(mode_name: str) -> bool:
        return mode_name.lower() == "transcript"

    @staticmethod
    def _long_recording_mode(mode_name: str) -> str:
        normalized = mode_name.lower()
        if normalized == "translation":
            return "translate"
        if normalized in {"transcript", "translate", "clean_transcript"}:
            return normalized
        return "transcript"

    def toggle_long_recording(self) -> None:
        if self._recording and getattr(self, "_recording_style", "") == "long":
            self.stop_recording()
            return
        self.start_recording("record_new_note", recording_style="long")

    def start_recording(self, context_action: str, recording_style: str = "hold") -> None:
        with self._lock:
            if self._recording or self._processing:
                return
            self._recording = True
            self._recording_context = context_action
            self._recording_style = recording_style
            requested_mode_name, _ = self._active_mode_info()
            if recording_style == "long":
                self._recording_mode_name = self._long_recording_mode(requested_mode_name)
                if self._recording_mode_name != requested_mode_name.lower():
                    print(f"[MODE] Long recording does not support '{requested_mode_name}', using transcript.")
                    overlay.show("Long recording: transcript")
            else:
                self._recording_mode_name = requested_mode_name
            db_mode = modes_service.get_mode(self._recording_mode_name)
            mode_id = db_mode["id"] if db_mode else None
            self._live_transcript = (
                recording_style == "long"
                or self._is_segmented_hold_mode(self._recording_mode_name)
            )

            while not self._frames.empty():
                self._frames.get_nowait()
            while not self._segment_queue.empty():
                self._segment_queue.get_nowait()
            self._recording_done.clear()
            self._segment_index = 0
            self._current_session = None

            try:
                self._open_audio_streams()
            except Exception as exc:
                self._recording = False
                self._processing = False
                self._recording_done.set()
                print(f"[ERROR] Failed to open audio input: {exc}")
                overlay.show("Audio input failed")
                return
            if self._live_transcript:
                self._processing = True
                if recording_style == "long":
                    segment_min_sec = self.cfg.long_segment_min_sec
                    segment_target_sec = self.cfg.long_segment_max_sec
                    segment_max_sec = self.cfg.long_segment_max_sec
                    force_split_sec = self.cfg.long_segment_max_sec
                else:
                    segment_min_sec = self.cfg.transcript_segment_min_sec
                    segment_target_sec = self.cfg.transcript_segment_target_sec
                    segment_max_sec = self.cfg.transcript_segment_max_sec
                    force_split_sec = self.cfg.transcript_segment_max_sec + 2.0

                self._current_session = TranscriptSession(
                    context_action=context_action,
                    mode_name=self._recording_mode_name,
                    mode_id=mode_id,
                    requested_mode_name=requested_mode_name,
                    copy_results=recording_style != "long",
                    realtime_paste=recording_style != "long",
                    use_previous_output=recording_style == "long",
                    note_separator=" " if recording_style == "long" else "\n",
                    segment_min_sec=segment_min_sec,
                    segment_target_sec=segment_target_sec,
                    segment_max_sec=segment_max_sec,
                    force_split_sec=force_split_sec,
                )
                threading.Thread(target=self._segment_transcript_audio, daemon=True).start()
                threading.Thread(target=self._process_transcript_segments, daemon=True).start()
                if recording_style == "long":
                    print(f"[REC] Long recording started in {self._recording_mode_name} mode...")
                    overlay.show(f"Recording: {self._recording_mode_name}")
                else:
                    print("[REC] Transcript recording started with live phrase splitting...")
            else:
                print("[REC] Recording started...")

    def stop_recording(self) -> None:
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            self._processing = True
            context_action = getattr(self, "_recording_context", "new_note")

        self._close_audio_streams()

        self._recording_done.set()
        if getattr(self, "_live_transcript", False):
            if getattr(self, "_recording_style", "") == "long":
                print("[REC] Long recording stopped. Waiting for segment queue...")
                overlay.show("Recording stopped")
            else:
                print("[REC] Recording stopped. Waiting for transcript queue...")
        else:
            print("[REC] Recording stopped. Processing audio via server...")
            threading.Thread(target=self._process_audio, args=(context_action,), daemon=True).start()

    def _collect_audio(self) -> Optional[np.ndarray]:
        chunks = []
        while not self._frames.empty():
            chunks.append(self._frames.get_nowait())
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0)

    def _prompt_content(self, mode_name: str | None = None) -> str:
        mode_name = mode_name or settings_service.get_active_mode()
        db_mode = modes_service.get_mode(mode_name)
        if db_mode:
            prompt = db_mode["system_prompt"]
        else:
            prompt = BUILTIN_PROMPTS.get(mode_name, "Format the provided audio.")
        if "nothing was said" not in prompt.lower():
            prompt = f"{prompt.rstrip()}\n\n{EMPTY_AUDIO_INSTRUCTION}"
        return prompt

    def _encode_audio(self, audio: np.ndarray) -> str:
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.cfg.sample_rate, format="wav")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _request_audio_completion(self, audio: np.ndarray, prompt: str) -> str:
        audio_b64 = self._encode_audio(audio)

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

        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    def _rms(self, audio: np.ndarray) -> float:
        if audio.size == 0:
            return 0.0
        normalized = np.asarray(audio, dtype=np.float64)
        return float(np.sqrt(np.mean(normalized * normalized)))

    def _queue_transcript_segment(self, chunks: list[np.ndarray], peak_rms: float, reason: str) -> None:
        if not chunks:
            return
        audio = np.concatenate(chunks, axis=0)
        if len(audio) == 0:
            return
        duration = len(audio) / self.cfg.sample_rate
        if peak_rms < self.cfg.transcript_silence_rms * 0.45:
            print(f"[SEG] Skipped quiet {duration:.1f}s segment ({reason}).")
            return
        self._segment_index += 1
        self._segment_queue.put((self._segment_index, audio))
        print(f"[SEG] Queued transcript segment {self._segment_index} ({duration:.1f}s, {reason}).")

    def _segment_transcript_audio(self) -> None:
        session = self._current_session
        if session is None:
            self._segment_queue.put(None)
            return

        chunks: list[np.ndarray] = []
        total_frames = 0
        low_frames = 0
        peak_rms = 0.0

        while not self._recording_done.is_set() or not self._frames.empty():
            try:
                chunk = self._frames.get(timeout=0.05)
            except queue.Empty:
                continue

            chunks.append(chunk)
            frames = len(chunk)
            total_frames += frames
            rms = self._rms(chunk)
            peak_rms = max(peak_rms, rms)

            silence_threshold = max(self.cfg.transcript_silence_rms, peak_rms * 0.25)
            is_low = rms <= silence_threshold
            low_frames = low_frames + frames if is_low else 0

            duration = total_frames / self.cfg.sample_rate
            quiet_duration = low_frames / self.cfg.sample_rate
            had_speech = peak_rms >= self.cfg.transcript_speech_rms
            quiet_boundary = quiet_duration >= self.cfg.transcript_silence_sec
            split_on_pause = (
                duration >= session.segment_min_sec
                and quiet_boundary
                and had_speech
            )
            split_on_quiet_run = (
                duration >= session.segment_target_sec
                and quiet_boundary
            )
            split_on_max = (
                duration >= session.segment_max_sec
                and quiet_boundary
            )
            force_split = duration >= session.force_split_sec

            if split_on_pause or split_on_quiet_run or split_on_max or force_split:
                if force_split:
                    reason = "max duration"
                elif split_on_max:
                    reason = "quiet near max"
                elif split_on_pause:
                    reason = "pause"
                else:
                    reason = "quiet"
                self._queue_transcript_segment(chunks, peak_rms, reason)
                chunks = []
                total_frames = 0
                low_frames = 0
                peak_rms = 0.0

        self._queue_transcript_segment(chunks, peak_rms, "release")
        self._segment_queue.put(None)

    def _save_result(self, result: str, context_action: str, mode_name: str) -> int | None:
        if context_action == "record_new_note":
            db_mode = modes_service.get_mode(mode_name)
            mode_id = db_mode["id"] if db_mode else None
            nid = notes_service.create_note(result, mode_id=mode_id)
            print(f"[DB] Created new note (ID: {nid}).")
            overlay.show(f"Saved: Note {nid}")
            return nid

        if context_action == "record_append_latest":
            active_nid = settings_service.get_active_note_id()
            if active_nid:
                notes_service.append_to_note(active_nid, result)
                print(f"[DB] Appended to active note (ID: {active_nid}).")
                overlay.show(f"Appended to Note {active_nid}")
                return active_nid

            latest_nid = notes_service.get_latest_note_id()
            if latest_nid:
                notes_service.append_to_note(latest_nid, result)
                print(f"[DB] Appended to latest note (ID: {latest_nid}).")
                overlay.show(f"Appended to Note {latest_nid}")
                return latest_nid

            db_mode = modes_service.get_mode(mode_name)
            mode_id = db_mode["id"] if db_mode else None
            nid = notes_service.create_note(result, mode_id=mode_id)
            print(f"[DB] Created fallback note (ID: {nid}).")
            overlay.show(f"Saved: Note {nid}")
            return nid

        return None

    def _save_transcript_result(self, result: str, session: TranscriptSession) -> None:
        if session.note_id is None:
            if session.context_action == "record_new_note":
                session.note_id = notes_service.create_note(result, mode_id=session.mode_id)
                print(f"[DB] Created new note (ID: {session.note_id}).")
                if session.copy_results:
                    overlay.show(f"Saved: Note {session.note_id}")
                return

            active_nid = settings_service.get_active_note_id()
            latest_nid = notes_service.get_latest_note_id()
            session.note_id = active_nid or latest_nid
            if session.note_id is None:
                session.note_id = notes_service.create_note(result, mode_id=session.mode_id)
                print(f"[DB] Created fallback note (ID: {session.note_id}).")
                if session.copy_results:
                    overlay.show(f"Saved: Note {session.note_id}")
                return

        separator = session.note_separator
        if separator == " " and result[:1] in ".,?!;:":
            separator = ""
        notes_service.append_to_note(session.note_id, result, separator=separator)
        print(f"[DB] Appended transcript segment to note (ID: {session.note_id}).")
        if session.copy_results:
            overlay.show(f"Transcript -> Note {session.note_id}")

    def _copy_and_maybe_paste(self, result: str, realtime_paste: bool, paste_suffix: str = "") -> None:
        pyperclip.copy(f"{result}{paste_suffix}")
        print("[OK] Output copied to clipboard.")
        if realtime_paste and settings_service.is_autopaste_enabled():
            autopaste.trigger_paste()
            print("[OK] Autopaste emitted.")

    def _long_segment_prompt(self, session: TranscriptSession) -> str:
        if session.mode_name == "translate":
            task = (
                "Translate the Polish audio segment into natural, fluent English. "
                "Preserve the original meaning, context, and tone."
            )
        elif session.mode_name == "clean_transcript":
            task = (
                "Transcribe the audio segment, remove filler words, lightly fix grammar, "
                "and make the sentence flow slightly better while staying very close to the speaker's words."
            )
        else:
            task = (
                "Transcribe the audio segment accurately with normal spelling and punctuation. "
                "Do not summarize or interpret."
            )

        previous = session.previous_output.strip() or "(none)"
        return (
            "You are processing one audio segment from a longer note.\n\n"
            f"Task: {task}\n\n"
            "Previous segment output, for continuity only:\n"
            f"{previous}\n\n"
            "Return only the text that should be appended for the current audio segment.\n"
            "Do not repeat text that already appears in the previous segment output.\n"
            "If the previous segment ended mid-sentence, continue naturally.\n"
            "It is acceptable to output nothing only if nothing was said in this audio segment."
        )

    def _segment_prompt(self, session: TranscriptSession) -> str:
        if session.use_previous_output:
            return self._long_segment_prompt(session)
        return self._prompt_content(session.mode_name)

    def _process_transcript_segments(self) -> None:
        session = self._current_session
        if session is None:
            with self._lock:
                self._processing = False
            return

        try:
            while True:
                item = self._segment_queue.get()
                if item is None:
                    break
                index, audio = item
                try:
                    print(f"[REQ] Processing transcript segment {index}...")
                    prompt = self._segment_prompt(session)
                    result = self._request_audio_completion(audio, prompt)
                except Exception as exc:
                    print(f"[ERROR] Transcript segment {index} failed: {exc}")
                    continue

                if not result:
                    print(f"[WARN] Transcript segment {index} returned empty output.")
                    continue

                if session.copy_results:
                    paste_suffix = "" if result.endswith((" ", "\n")) else " "
                    self._copy_and_maybe_paste(
                        result,
                        realtime_paste=session.realtime_paste,
                        paste_suffix=paste_suffix,
                    )
                self._save_transcript_result(result, session)
                session.previous_output = result
                if session.copy_results:
                    print("\a", end="")
        finally:
            with self._lock:
                self._processing = False
                self._current_session = None

    def _process_audio(self, context_action: str) -> None:
        try:
            audio = self._collect_audio()
            if audio is None or len(audio) == 0:
                print("[INFO] No audio captured.")
                return

            mode_name = getattr(self, "_recording_mode_name", settings_service.get_active_mode())
            prompt = self._prompt_content(mode_name)
            result = self._request_audio_completion(audio, prompt)
            if not result:
                print("[WARN] Server returned empty output.")
                return

            self._copy_and_maybe_paste(result, realtime_paste=True)
            self._save_result(result, context_action, mode_name)

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
    parser.add_argument("--input-device", default=None, help="Primary sounddevice input device index or name")
    parser.add_argument("--secondary-input-device", default=None, help="Optional second input device to mix in")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--transcript-segment-min-sec", type=float, default=2.5)
    parser.add_argument("--transcript-segment-target-sec", type=float, default=5.0)
    parser.add_argument("--transcript-segment-max-sec", type=float, default=8.0)
    parser.add_argument("--transcript-silence-sec", type=float, default=0.35)
    parser.add_argument("--transcript-silence-rms", type=float, default=0.010)
    parser.add_argument("--transcript-speech-rms", type=float, default=0.018)
    parser.add_argument("--long-segment-min-sec", type=float, default=1.5)
    parser.add_argument("--long-segment-max-sec", type=float, default=30.0)
    args = parser.parse_args()

    return AppConfig(
        server_url=args.server_url,
        sample_rate=args.sample_rate,
        channels=args.channels,
        input_device=args.input_device if args.input_device is not None else settings_service.get_setting("audio_input_device"),
        secondary_input_device=(
            args.secondary_input_device
            if args.secondary_input_device is not None
            else settings_service.get_setting("audio_secondary_input_device")
        ),
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        transcript_segment_min_sec=args.transcript_segment_min_sec,
        transcript_segment_target_sec=args.transcript_segment_target_sec,
        transcript_segment_max_sec=args.transcript_segment_max_sec,
        transcript_silence_sec=args.transcript_silence_sec,
        transcript_silence_rms=args.transcript_silence_rms,
        transcript_speech_rms=args.transcript_speech_rms,
        long_segment_min_sec=args.long_segment_min_sec,
        long_segment_max_sec=args.long_segment_max_sec,
    )

def _toggle_autopaste():
    val = not settings_service.is_autopaste_enabled()
    settings_service.set_autopaste_enabled(val)
    print(f"[CONFIG] Autopaste toggled to {'ON' if val else 'OFF'}")
    overlay.show(f"Autopaste: {'ON' if val else 'OFF'}")


def _ensure_builtin_modes() -> None:
    for name, prompt in BUILTIN_PROMPTS.items():
        if not modes_service.get_mode(name):
            modes_service.add_mode(name, prompt)


def _ensure_default_keybinds() -> None:
    binds = hotkeys_service.get_keybinds()
    if "toggle_long_recording" not in binds:
        hotkeys_service.set_keybind("toggle_long_recording", "f6")


def main() -> None:
    cfg = parse_args()
    _ensure_builtin_modes()
    _ensure_default_keybinds()
    app = PushToTalkFormatter(cfg)

    print("=== KeyNote Push-to-Talk Formatter (DB Server Mode) ===")
    print(f"Server: {cfg.server_url}")
    primary_label = cfg.input_device if cfg.input_device else "default input"
    if cfg.secondary_input_device:
        print(f"Audio input: {primary_label} + {cfg.secondary_input_device}")
    else:
        print(f"Audio input: {primary_label}")

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
            elif action == "toggle_long_recording":
                keyboard.add_hotkey(combo, app.toggle_long_recording)
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
