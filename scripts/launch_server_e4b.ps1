$ErrorActionPreference = "Stop"

$server = $env:LLAMA_SERVER
if (-not $server) {
    $server = "D:\llama.cpp\build\bin\Release\llama-server.exe"
}

$model = $env:KEYNOTE_E4B_MODEL
if (-not $model) {
    $model = "D:\huggingface_cache\hub\models--unsloth--gemma-4-E4B-it-GGUF\snapshots\ce152932ac27bc40bc9c727386760424d50bb456\gemma-4-E4B-it-Q4_K_M.gguf"
}

$mmproj = $env:KEYNOTE_E4B_MMPROJ
if (-not $mmproj) {
    $mmproj = "D:\huggingface_cache\hub\models--unsloth--gemma-4-E4B-it-GGUF\snapshots\ce152932ac27bc40bc9c727386760424d50bb456\mmproj-BF16.gguf"
}

# Keep continuous batching enabled so phrase-sized transcript chunks can queue
# while earlier chunks are still being processed.
& $server `
    -m $model `
    --mmproj $mmproj `
    --jinja `
    --image-min-tokens 300 `
    --image-max-tokens 512 `
    --port 8080 `
    -ngl 99 `
    -np 4 `
    --cont-batching `
    -b 2048 `
    -ub 512 `
    -c 16384
