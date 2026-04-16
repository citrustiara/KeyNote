# Development Plan: "Push-to-Talk" Smart Formatter using Gemma 4 E2B

## 1. Executive Summary
This document outlines the architecture and implementation plan for a lightweight, local, native-audio transcription and formatting tool. The application will listen for a global keyboard shortcut (Push-to-Talk), capture audio via the microphone, and pass the raw audio directly into **Gemma 4 E2B** using **llama.cpp**. The LLM will process the audio, format the speech according to predefined prompts (e.g., Slack message, email, project requirements), and automatically place the output into the user's system clipboard for immediate pasting.

## 2. Core Architecture & Data Flow

### The Pipeline
1. **Idle State:** The application runs in the background, consuming minimal CPU/RAM.
2. **Key Press:** Global hotkey is held down -> Audio recording stream begins.
3. **Key Release:** Audio recording stops -> Saved to a temporary RAM disk or fast temporary file (`.wav`).
4. **Inference:** The audio file and a formatting prompt are sent to the local `llama.cpp` server/CLI.
5. **Output Generation:** Gemma 4 E2B processes the audio natively and outputs the formatted text.
6. **Clipboard Injection:** The text is piped to the OS clipboard, and a notification sound/UI pop-up alerts the user.

---

## 3. Tech Stack & Required Libraries

The tool will be built as a Python application acting as a wrapper/controller for the `llama.cpp` engine. 

### Python Dependencies
* **`pynput`** or **`keyboard`**: For global system-wide hotkey detection (detecting key-down and key-up events).
* **`sounddevice`** and **`soundfile`**: For low-latency, high-quality audio capture. `sounddevice` allows recording directly into NumPy arrays, and `soundfile` handles fast `.wav` export.
* **`pyperclip`**: For cross-platform clipboard injection.
* **`httpx`** or **`requests`**: If interfacing with `llama-server` via local HTTP requests.
* **`pystray`** (Optional): For creating a system tray icon to switch between formatting modes (e.g., "Email Mode", "Jira Mode").

### Core Engine
* **`llama.cpp`**: Compiled with Metal (macOS) or CUDA (Windows/Linux) support for hardware acceleration.
* **Model Weights (GGUF)**:
    * `gemma-4-E2B-it-Q4_K_M.gguf` (The LLM model)
    * `mmproj-gemma-4-audio-f16.gguf` (The Multimodal Projector for audio)

---

## 4. Implementation Phases

### Phase 1: Engine Setup & Validation
Before writing the wrapper, the core inference pipeline must be validated.
1. Compile `llama.cpp` from source with the appropriate hardware acceleration flags (`LLAMA_METAL=1` or `LLAMA_CUBLAS=1`).
2. Download the Gemma 4 E2B quantized model and its specific audio multimodal projector.
3. Test inference manually via terminal:
   ```bash
   ./llama-mtmd-cli -m models/gemma-4-E2B-it-Q4.gguf \
     --mmproj models/mmproj-gemma-4-audio.gguf \
     -f prompt_template.txt \
     --audio test_recording.wav \
     -n 256 --temp 0.2