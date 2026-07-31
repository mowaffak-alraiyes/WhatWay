#!/bin/bash
# BridgeCare local runner — loads .env then starts Streamlit
set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "Loaded .env"
else
  echo "No .env yet — copy .env.example → .env"
fi

# Mirror Neon/Twilio into Streamlit secrets if missing
mkdir -p .streamlit
if [ ! -f .streamlit/secrets.toml ]; then
  cat > .streamlit/secrets.toml <<EOF
OLLAMA_BASE_URL = "${OLLAMA_BASE_URL:-http://localhost:11434/v1}"
OLLAMA_MODEL = "${OLLAMA_MODEL:-llama3}"
NEON_DB_HOST = "${NEON_DB_HOST:-}"
NEON_DB_NAME = "${NEON_DB_NAME:-}"
NEON_DB_USER = "${NEON_DB_USER:-}"
NEON_PASSWORDLESS_TOKEN = "${NEON_PASSWORDLESS_TOKEN:-}"
NEON_SSLMODE = "${NEON_SSLMODE:-require}"
TWILIO_ACCOUNT_SID = "${TWILIO_ACCOUNT_SID:-}"
TWILIO_AUTH_TOKEN = "${TWILIO_AUTH_TOKEN:-}"
TWILIO_WHATSAPP_FROM = "${TWILIO_WHATSAPP_FROM:-whatsapp:+14155238886}"
EOF
  echo "Wrote .streamlit/secrets.toml from .env"
fi

if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Warning: Ollama not reachable at :11434 — run: ollama serve"
fi

source .venv/bin/activate 2>/dev/null || true
exec streamlit run Aidr.py
