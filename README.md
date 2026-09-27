# Raziel — Telegram Media Pipeline Bot

<p align="center">
  <img src="assets/raziel-avatar.png" alt="Raziel" width="300">
</p>

![Version](https://img.shields.io/badge/version-v6.10-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Telegram-26A5E4)
![Backend](https://img.shields.io/badge/media-yt--dlp-red)
![Processing](https://img.shields.io/badge/processing-FFmpeg-black)
![License](https://img.shields.io/badge/license-Typezer%E2%88%85%20All%20Rights%20Reserved-darkred)

**Raziel** is a queue-driven Telegram bot for downloading, processing, routing, and reposting media with a quiet-first group-chat workflow. It combines `yt-dlp`, FFmpeg, Telegram commands, automatic link ingestion, reply-driven controls, persistent queue state, weather utilities, caption-first video synopsis generation, optional local AI summarization, and optional local Telegram Bot API support for large uploads.

Raziel is designed to stay useful without becoming noisy: ordinary downloads favor concise captions and transient status messages, while richer source metadata is available on demand.

## Highlights

- Persistent single-worker download queue with retry/failure tracking.
- Video, HD, full-quality, audio, and clip workflows.
- Automatic link ingestion in groups, with per-chat opt-out controls.
- Reply-driven commands that preserve conversation context.
- Quiet-first metadata architecture with explicit `*meta` commands.
- Interactive quality-selection buttons through `/ui`.
- yt-dlp-backed platform support with optional strict domain validation.
- FFmpeg validation, clipping, audio extraction, and fallback compression.
- Persistent deduplication and recent-history tracking.
- Watch-folder and direct CLI ingestion.
- Optional local Telegram Bot API support for large uploads.
- Weather and forecast utilities powered by Open-Meteo.
- Caption-first `/synopsis` and `/rsynopsis` with an optional local Qwen/llama.cpp backend and automatic extractive fallback.
- Owner/admin controls for status, cleanup, queue management, reload, restart, and shutdown.

## Media workflow

```text
Telegram / CLI / Watch Folder
            │
            ▼
     Validate + Preflight
            │
            ▼
       Persistent Queue
            │
            ▼
         yt-dlp
            │
            ▼
     FFmpeg Processing
            │
            ▼
      Telegram Upload
            │
            ▼
       Route / Archive
```

Runtime data is kept outside the tracked source tree when `BASE_DIR` is configured accordingly. Raziel maintains state, downloads, logs, completed media, failures, cookies, and the watch folder beneath that runtime directory.

## Commands

### Download and media commands

| Command | Purpose |
| --- | --- |
| `/dl <url>` | Download using the configured default quality. |
| `/hd <url>` | Download using the configured HD quality. |
| `/full <url>` | Download the best available quality. |
| `/audio <url>` | Extract/download audio. |
| `/clip <url> <start> <end>` | Download and create a time-bounded clip. |
| `/ui <url>` | Open interactive quality buttons. |
| `/queue` | Show the current and pending queue. |

### Reply-driven commands

Reply to a message containing a media URL with:

```text
/rdl
/rhd
/rfull
/raudio
/rui
```

Raziel keeps the resulting workflow attached to the original conversation whenever Telegram permits it.


### Video synopsis

Raziel can build a concise synopsis from video captions:

```text
/synopsis <url>
/rsynopsis
```

`/rsynopsis` reads the URL from the message being replied to. English human
captions are preferred when available, with automatic English captions as a
fallback.

The optional local AI path uses an OpenAI-compatible `llama.cpp` server with a
small Qwen model. If that service is unavailable, Raziel automatically falls
back to its extractive summarizer.

See [`docs/LOCAL_LLM.md`](docs/LOCAL_LLM.md) for local model setup, systemd,
resource guidance, environment overrides, and troubleshooting.


### Metadata-on-demand

The quiet-first commands above avoid unnecessary extra context. Use the metadata variants when you explicitly want source context:

```text
/dlmeta
/hdmeta
/fullmeta
/audiometa
/rdlmeta
/rhdmeta
/rfullmeta
/raudiometa
```

### Utilities

```text
/weather <place>
/forecast <place>
/whoami
/help
```

Raziel also supports its configured mention aliases for supported conversational utilities.

### Administration

Admin/owner commands include:

```text
/lastusers
/stats
/status
/groups
/cleanup
/failures
/retrylast
/reload
/restart
/clearqueue
/leave
/leavechat
/delete
/del
/rm
/shutdown
```

## Supported sources

Raziel uses `yt-dlp` as its extraction backend. Its built-in platform presets include:

- YouTube
- Instagram
- Reddit
- TikTok
- X / Twitter
- Facebook
- BitChute

By default, the example configuration enables YouTube and Instagram. Additional presets or one-off domains can be enabled in configuration. When `STRICT_PLATFORM_VALIDATION = False`, Raziel may pass other URLs to yt-dlp after media preflight instead of limiting input to the configured preset list.

Availability is ultimately determined by the installed yt-dlp version and the source site. A listed platform is not a guarantee that every URL or protected/private item is downloadable.

## Requirements

- Python 3.10+
- `python-telegram-bot` 22+
- `yt-dlp`
- FFmpeg / ffprobe available in `PATH`
- Telegram bot token from BotFather
- Optional: locally hosted Telegram Bot API for large-file workflows
- Optional: local `llama.cpp` server for AI-assisted caption synopsis generation

Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Copy the safe example and keep the real configuration untracked:

```bash
cp config/razielrc_EXAMPLE.py config/razielrc.py
```

At minimum, configure:

```python
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ALLOWED_USER_ID = 123456789
```

The real `config/ytbotrc.py` is excluded by `.gitignore`.

Raziel resolves configuration in this order:

1. `RAZIEL_CONFIG`, when the environment variable points to a config file.
2. `config/ytbotrc.py` inside the Raziel repository.
3. The legacy sibling `../config/ytbotrc.py` location for existing deployments.

For a private external configuration:

```bash
export RAZIEL_CONFIG="$HOME/.config/raziel/razielrc.py"
python raziel.py
```

See [`config/razielrc_EXAMPLE.py`](config/razielrc_EXAMPLE.py) and [`docs/SETUP.md`](docs/SETUP.md) for the full configuration and deployment notes.

## Running Raziel

Interactive Telegram mode:

```bash
python raziel.py
```

Direct CLI download:

```bash
python raziel.py --url "https://example.com/media"
```

Direct audio download:

```bash
python raziel.py --audio "https://example.com/media"
```

## Runtime directories

`BASE_DIR` controls Raziel's runtime storage root. A typical configuration might be:

```python
BASE_DIR = "$HOME/.local/share/raziel"
```

Raziel creates and uses directories such as:

```text
state/
downloads/
logs/
done/video/
done/audio/
done/failed/
watch/
cookies/
```

Do not commit runtime state, cookies, downloaded media, logs, or the live configuration.

## Privacy and access model

Raziel can inspect ordinary non-command messages because automatic link ingestion and mention handling depend on message content. This is different from a command-only Telegram bot.

Access controls are configurable. Private-chat use can remain owner-restricted while group behavior is controlled through bot permissions, user/admin configuration, platform validation, and per-chat auto-watch overrides.

Before deploying Raziel into a group, make sure participants understand the bot's automatic link behavior and configure Telegram/BotFather privacy settings consistently with the features you intend to use.

## Repository layout

```text
Raziel/
├── config/
│   └── ytbotrc_EXAMPLE.py
├── docs/
│   ├── ATTRIBUTION.md
│   ├── SETUP.md
│   └── ...
├── notes/                  # historical implementation/version notes
├── .gitignore
├── CHANGELOG.md
├── LICENSE.md
├── README.md
├── SECURITY.md
├── requirements.txt
└── ytbot.py
```

## Version history

Raziel's detailed implementation history is preserved under [`notes/`](notes/README.md). The current public-facing changes are summarized in [`CHANGELOG.md`](CHANGELOG.md).

## Responsible use

Raziel is a media-management tool. Users are responsible for complying with copyright law, source-site terms, Telegram rules, and any other restrictions that apply to media they access, download, process, or redistribute.

Raziel does not grant rights to third-party content merely because a source can technically be processed by yt-dlp.

## Third-party software and services

Raziel depends on or interoperates with projects and services that have their own licenses and terms, including Telegram, python-telegram-bot, yt-dlp, FFmpeg, and Open-Meteo. See [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md).

## License

Copyright © 2026 **Typezer∅**. All rights reserved.

Raziel's source is publicly viewable, but Raziel is **not open-source software** and is not released under a permissive or copyleft software license. See [`LICENSE.md`](LICENSE.md) for the complete source-code license notice.
