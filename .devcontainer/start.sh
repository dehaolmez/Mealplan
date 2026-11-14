#!/usr/bin/env bash
# Codespace her açıldığında Meall'ı 8080 portunda başlatır (arayüz + API tek adreste).
set -euo pipefail
cd "$(dirname "$0")/../backend"
mkdir -p "$HOME/.meall"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
export MEALBIRD_DATABASE_URL="sqlite:///$HOME/.meall/meall.db"
export MEALBIRD_STATIC_DIR="$(cd ../frontend/dist && pwd)"
export MEALBIRD_COOKIE_SECURE=true
if [ -n "${CODESPACE_NAME:-}" ]; then
  export MEALBIRD_PUBLIC_BASE_URL="https://${CODESPACE_NAME}-8080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
fi
setsid nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips='*' \
  > "$HOME/.meall/server.log" 2>&1 < /dev/null &
echo "Meall başlatıldı: port 8080 (günlük: ~/.meall/server.log)"
