#!/usr/bin/env bash
# Codespace ilk kurulduğunda: arka uç bağımlılıkları + arayüz derlemesi
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv backend/.venv
backend/.venv/bin/pip install -q --upgrade pip
backend/.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm ci --no-audit --no-fund && npm run build)
echo "Kurulum tamam."
