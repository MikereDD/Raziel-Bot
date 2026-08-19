#!/usr/bin/env bash
set -euo pipefail

: "${TELEGRAM_API_ID:?Set TELEGRAM_API_ID in your environment}"
: "${TELEGRAM_API_HASH:?Set TELEGRAM_API_HASH in your environment}"

BOT_API_BIN="${TELEGRAM_BOT_API_BIN:-telegram-bot-api}"
BOT_API_DIR="${TELEGRAM_BOT_API_DIR:-$HOME/.local/share/telegram-bot-api}"

mkdir -p "$BOT_API_DIR"

exec "$BOT_API_BIN" \
  --api-id "$TELEGRAM_API_ID" \
  --api-hash "$TELEGRAM_API_HASH" \
  --local \
  --http-port 8081 \
  --dir "$BOT_API_DIR"
