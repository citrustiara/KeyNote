# KeyNote

Local push-to-talk formatter for Gemma 4 E2B + `llama.cpp`.

## What it does
- Hold a global hotkey to record microphone audio
- Release the key to run local audio inference (`llama-mtmd-cli`)
- Formats output using selected prompt mode (`slack`, `email`, `requirements`)
- Copies final text directly to clipboard

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
python keynote_ptt.py \
  --model /path/to/gemma-4-E2B-it-Q4_K_M.gguf \
  --mmproj /path/to/mmproj-gemma-4-audio-f16.gguf
```

Optional flags:
- `--llama-cli` path to `llama-mtmd-cli` (default assumes it is in PATH)
- `--hold-key f8` change push-to-talk key
- `--mode slack|email|requirements` default formatting mode

Runtime hotkeys:
- Hold configured key (default `F8`) to record
- `Ctrl+Alt+1` -> Slack mode
- `Ctrl+Alt+2` -> Email mode
- `Ctrl+Alt+3` -> Requirements mode
- `Esc` -> Exit
