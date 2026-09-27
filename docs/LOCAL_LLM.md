# Local LLM Synopsis Backend

Raziel v6.10 adds a caption-first synopsis workflow that can use a local
`llama.cpp` server for AI-assisted summaries without requiring a hosted AI API.

The default local backend is configured for:

- `llama.cpp` OpenAI-compatible HTTP server
- Qwen3 1.7B GGUF
- `Q4_K_M` quantization
- `127.0.0.1:8082`
- 4096-token context
- one parallel slot

The synopsis feature remains usable when the local LLM is unavailable. Raziel
falls back automatically to its built-in extractive summarizer.

## Commands

```text
/synopsis <url>
/rsynopsis
```

`/synopsis` accepts a supported video URL.

`/rsynopsis` is reply-only and extracts the URL from the replied-to message.

Raziel prefers English human captions when available and can fall back to
automatic English captions. Automatic-caption results include a warning because
names, numbers, and specialized terms can be transcribed incorrectly.

## How the pipeline works

```text
Video URL
   │
   ▼
Caption extraction
   │
   ▼
Caption cleanup / deduplication
   │
   ▼
~3500-character transcript chunks
   │
   ▼
Local Qwen chunk summaries
   │
   ▼
Final attributed 5-bullet reduction
   │
   ▼
Telegram synopsis
```

Long synopsis work runs in the background so normal Telegram update processing
and inline commands can remain responsive.

## Build llama.cpp

A normal local llama.cpp build is sufficient. See the upstream llama.cpp project
for platform-specific build instructions.

The examples below assume the executable is available as:

```text
/path/to/llama.cpp/build/bin/llama-server
```

## Manual server launch

Example:

```bash
cd /path/to/llama.cpp

./build/bin/llama-server \
  -hf ggml-org/Qwen3-1.7B-GGUF:Q4_K_M \
  --host 127.0.0.1 \
  --port 8082 \
  --ctx-size 4096 \
  --parallel 1
```

Verify the server:

```bash
curl http://127.0.0.1:8082/health
```

Expected response:

```json
{"status":"ok"}
```

Binding to `127.0.0.1` keeps the unauthenticated llama.cpp HTTP endpoint local to
the machine. Do not expose it to a LAN or the public internet without adding
appropriate authentication and network controls.

## Environment overrides

Raziel uses these optional environment variables:

```text
RAZIEL_LLM_URL
RAZIEL_LLM_HEALTH_URL
RAZIEL_LLM_MODEL
RAZIEL_LLM_TIMEOUT
```

Built-in defaults:

```text
RAZIEL_LLM_URL=http://127.0.0.1:8082/v1/chat/completions
RAZIEL_LLM_HEALTH_URL=http://127.0.0.1:8082/health
RAZIEL_LLM_MODEL=default
RAZIEL_LLM_TIMEOUT=120
```

Example override:

```bash
export RAZIEL_LLM_URL="http://127.0.0.1:8082/v1/chat/completions"
export RAZIEL_LLM_HEALTH_URL="http://127.0.0.1:8082/health"
python raziel.py
```

## systemd

A public-safe example unit is provided at:

```text
docs/etc/systemd/system/raziel-llama.service
```

Copy it locally, replace the placeholder user/path values, then install it:

```bash
sudo cp docs/etc/systemd/system/raziel-llama.service \
  /etc/systemd/system/raziel-llama.service

sudo systemctl daemon-reload
sudo systemctl enable --now raziel-llama.service
```

Verify:

```bash
systemctl status raziel-llama.service --no-pager
curl http://127.0.0.1:8082/health
```

## Raspberry Pi / low-memory hosts

On an 8 GB Raspberry Pi 5, the 1.7B Q4 model can run successfully when the
server context is constrained. A very large automatic context may consume most
available RAM and trigger the Linux OOM killer.

The known-working conservative settings are:

```text
--ctx-size 4096
--parallel 1
```

If memory pressure remains high, also consider smaller batch sizes:

```text
--batch-size 256
--ubatch-size 128
```

Do not add swap as the first fix for an oversized context. Constrain the model
context and batching first.

## Fallback behavior

If the configured LLM health endpoint is unavailable, Raziel uses the built-in
extractive summarizer instead of failing the synopsis command.

If the local LLM becomes unavailable after selection, the default synopsis path
also falls back when the backend raises a synopsis error.

This means a failed or stopped local model does not disable caption-based
synopsis generation entirely.

## Troubleshooting

### Synopsis returns very quickly with sentence-like raw excerpts

The extractive fallback may be active. Check:

```bash
curl http://127.0.0.1:8082/health
```

Also verify that the deployed `raziel_synopsis.py` points to port `8082`.

### llama-server is killed during startup

Check the kernel log:

```bash
dmesg | tail -100
```

If the process was OOM-killed, use the constrained server settings shown above.

### Telegram reports conflicting getUpdates requests

Only one polling Raziel instance can use a Telegram bot token at a time. Stop
duplicate Raziel processes before testing another checkout.

### Inline commands stop responding during a synopsis

Current v6.10 code schedules long synopsis jobs as background tasks. Make sure
the deployed `raziel.py` is from v6.10 or later.

## Security notes

- Keep the llama.cpp listener on `127.0.0.1` unless you intentionally secure it.
- Do not put Telegram bot tokens, Telegram API credentials, or private runtime
  data in the LLM service unit.
- Do not commit live configuration, logs, cookies, or model credentials.
