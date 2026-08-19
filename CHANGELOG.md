# Changelog

This file summarizes public-facing Raziel changes. Detailed historical design
and implementation notes are preserved in [`notes/`](notes/README.md).

## 6.9

- Adopted quiet-first media captions for normal download commands.
- Kept rich source context available through explicit metadata commands.
- Preserved reply-driven video/audio workflows and legacy command behavior.
- Continued persistent queue, deduplication, failure/retry, and routing systems.
- Continued configurable automatic group link ingestion and media preflight.
- Continued weather/forecast, inline/mention, watch-folder, and CLI utilities.

### GitHub preparation

- Reworked the public README and project presentation.
- Replaced the previous WTFPL notice with the Typezer∅ source-code license
  notice; Raziel is source-visible but not open source.
- Added repository security guidance and third-party attribution documentation.
- Added a repository `.gitignore` for secrets, runtime state, cookies, media,
  logs, virtual environments, and build artifacts.
- Corrected `STRICT_PLATFORM_VALIDATION = False` in the example configuration;
  the prior trailing comma created a truthy single-item tuple.
- Added standalone-repository config discovery while preserving the legacy
  sibling-config location as a fallback.
- Generalized deployment documentation so it does not depend on a specific
  developer machine/account layout.
