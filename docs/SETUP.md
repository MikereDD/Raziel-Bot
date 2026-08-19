# Raziel Setup Guide

This guide covers a standalone Raziel installation on Linux. Adjust package-manager and service paths for your own system.

## 1. System dependencies

Raziel requires Python 3.10+ and FFmpeg/ffprobe.

On Arch Linux:

```bash
sudo pacman -S --needed python ffmpeg git
```

`ffprobe` is provided with FFmpeg on a standard Arch installation.

A current JavaScript runtime can also help yt-dlp with extractors that require one:

```bash
sudo pacman -S --needed nodejs
```

## 2. Python environment

From the Raziel repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The `.venv/` directory is intentionally ignored by Git.

## 3. Configuration

For a simple local installation:

```bash
cp config/ytbotrc_EXAMPLE.py config/ytbotrc.py
chmod 600 config/ytbotrc.py
```

Edit `config/ytbotrc.py` and set at least:

```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ALLOWED_USER_ID = 123456789
```

The live config is excluded by `.gitignore`.

For a config completely outside the repository:

```bash
mkdir -p "$HOME/.config/raziel"
cp config/ytbotrc_EXAMPLE.py "$HOME/.config/raziel/ytbotrc.py"
chmod 600 "$HOME/.config/raziel/ytbotrc.py"
export RAZIEL_CONFIG="$HOME/.config/raziel/ytbotrc.py"
```

Raziel also preserves compatibility with the older sibling `../config/ytbotrc.py` deployment layout.

## 4. Runtime directory

The example configuration stores runtime data under:

```text
$HOME/.local/share/raziel
```

Raziel creates the needed `state`, `downloads`, `logs`, `done`, `watch`, and `cookies` subdirectories automatically.

Keep this runtime directory outside version control.

## 5. Run Raziel

```bash
source .venv/bin/activate
python ytbot.py
```

If you use an external configuration:

```bash
RAZIEL_CONFIG="$HOME/.config/raziel/ytbotrc.py" python ytbot.py
```

## 6. Optional local Telegram Bot API

Raziel can use a locally hosted Telegram Bot API endpoint for large-file workflows. This is optional; leave `LOCAL_BOT_API_URL` and `LOCAL_BOT_API_FILE_URL` empty if you are using Telegram's normal Bot API endpoints.

When using a local Bot API server, obtain your Telegram `api_id` and `api_hash` through Telegram's official developer process and keep both values private.

Example configuration:

```python
LOCAL_BOT_API_URL = "http://127.0.0.1:8081/bot"
LOCAL_BOT_API_FILE_URL = "http://127.0.0.1:8081/file/bot"
```

The template files under `docs/etc/` and `docs/scripts/` contain placeholders only. Replace the placeholders locally; never commit your real API credentials.

## 7. Validation

Check Python syntax:

```bash
python -m py_compile ytbot.py config/ytbotrc_EXAMPLE.py
```

Confirm FFmpeg tools are available:

```bash
ffmpeg -version
ffprobe -version
```

Start Raziel and confirm `/start`, `/help`, `/status` (admin), and a test media command behave as expected in your intended Telegram chat.

## 8. Troubleshooting

### Missing config

If Raziel reports that it cannot find its configuration, either create:

```text
config/ytbotrc.py
```

or set:

```bash
export RAZIEL_CONFIG="/absolute/path/to/ytbotrc.py"
```

### yt-dlp extraction failures

Update the installed dependency in the active virtual environment:

```bash
python -m pip install --upgrade yt-dlp
```

Source-site changes can break individual extractors independently of Raziel.

### FFmpeg/ffprobe unavailable

Install FFmpeg through your operating system package manager and ensure both commands are available in `PATH`.

### Upload timeout or size issues

Check Raziel's logs and verify `TELEGRAM_UPLOAD_TIMEOUT`. For the large-file workflow, also verify that your local Telegram Bot API server is actually running and that Raziel's local API URLs match it.

## Security checklist

- [ ] Real bot token is not in Git.
- [ ] Telegram API ID/hash are not in Git.
- [ ] Cookie files are private and untracked.
- [ ] Runtime logs/state/downloads are outside Git.
- [ ] Access-control lists contain only intended users/admins.
- [ ] Group auto-watch behavior is configured intentionally.
- [ ] Telegram bot permissions/privacy settings match the features you intend to use.
