# Security Policy

## Sensitive configuration

Raziel requires secrets and deployment-specific identifiers that must not be
committed to the repository. Keep the live configuration private and use
`config/ytbotrc_EXAMPLE.py` only as a template.

Never commit:

- Telegram bot tokens;
- Telegram API ID/API hash values;
- private cookies or browser-exported cookie files;
- private chat, group, or user identifiers when they are not intentionally
  public;
- runtime state, logs, queue/history files, or downloaded media; or
- credentials embedded in scripts, service files, URLs, or shell history.

If a credential is accidentally committed, treat it as compromised even if
the commit is later removed. Revoke or rotate the credential first, then clean
the repository history as appropriate.

## Deployment

Run Raziel with the minimum permissions needed for its configured features.
Keep the bot, Python dependencies, yt-dlp, FFmpeg, operating system, and any
local Telegram Bot API deployment maintained and patched.

Automatic link ingestion causes Raziel to inspect non-command messages that it
can receive in configured chats. Configure Telegram privacy/permissions and
Raziel's access controls intentionally for each deployment.

## Reporting a security issue

Do not publish bot tokens, private configuration, exploit details involving a
live deployment, or other sensitive data in a public GitHub issue.

Use a private contact method made available by the repository owner for
security-sensitive reports. Ordinary bugs that do not expose secrets or create
an active security risk may be reported through the repository's normal issue
tracker if one is enabled.
