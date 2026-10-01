# WhatWay: Refugee Resource Assistant

Find healthcare, education, and legal/shelter resources for refugee families in Illinois and Indiana, via web chat, and on WhatsApp once Meta Business verification clears.

> **Renamed from Aidr.** Environment variables moved from `AIDR_*` to `WHATWAY_*`. Existing deployments keep working: `core/env.py` copies any `AIDR_*` variable onto its `WHATWAY_*` twin at import time, and the new name always wins if both are set. Rename them in your host's settings when convenient, the shim is a transition aid, not a permanent contract.

## Design

The design system lives on a canvas: palette, type, logo, the browser assistant, whatway.org, the WhatsApp channel, and the motion spec. Tokens in short:

| Token | Hex | Use |
|---|---|---|
| Mist | `#F1F7F3` | page ground |
| Card | `#FFFFFF` | raised surfaces |
| Ink | `#10221B` | body text |
| Ink muted | `#4A5F55` | captions (contrast floor) |
| Spruce | `#0E6B54` | primary action, links |
| Pine | `#08432F` | giving, dark bands |
| Fern | `#2E9E6B` | graphics only, never text |

One hue, five steps: nothing is distinguished by colour alone. Badges differ by fill / outline / solid so they survive greyscale and colour-blindness. Controls are 44px minimum, radius 14; cards radius 18.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Ensure Ollama is running: ollama serve && ollama pull llama3
./run_app.sh
```

Open http://localhost:8501: try **Healthcare → dental 60629**.

## Search, RAG, and Ollama

WhatWay does not use an LLM as its database. Category, ZIP, language, hours,
and service matching stay deterministic so a model cannot invent a clinic or
silently ignore an eligibility constraint. Ollama is an optional local layer
for understanding conversational queries, translation, and one-sentence result
introductions.

For production, set `WHATWAY_LLM_PROVIDER=workers_ai` and configure the three
`CLOUDFLARE_*` values shown in `.env.example`. Search still works when the model
is unavailable. The planned RAG boundary and migration stages are documented in
[`docs/AI_ARCHITECTURE.md`](docs/AI_ARCHITECTURE.md).

## Setup and security checklist

1. Put secrets only in `.env` / `.streamlit/secrets.toml`, never commit them (both are gitignored).
2. Set `ADMIN_PASSWORD` before using the Streamlit admin page (no default password).
3. Set `TELEGRAM_ALLOWED_CHAT_IDS` for clinic ops; an empty allowlist rejects all Telegram commands.
4. WhatsApp dry-run logs mask phone numbers; conversation sessions key on hashed IDs.
5. SQL uses parameterized queries (`%s` + tuple). Do not interpolate user input into SQL.
6. FastAPI CORS defaults to localhost Streamlit; set `WHATWAY_CORS_ORIGINS` for deploy.
7. `/webhooks/whatsapp/simulate` is off unless `WHATWAY_ENABLE_SIMULATE=1`.
8. When `TWILIO_AUTH_TOKEN` is set, Twilio webhooks require a valid `X-Twilio-Signature`.

**Privacy:** We do not intend to store raw phone numbers or IPs in logs. Prefer hashed identifiers. Resource data is public clinic listings, not patient records.

## WhatsApp API (spike)

```bash
export WHATWAY_ENABLE_SIMULATE=1   # local smoke test only
uvicorn api.main:app --reload --port 8000
curl -X POST localhost:8000/webhooks/whatsapp/simulate \
  -H 'content-type: application/json' \
  -d '{"from":"test","body":"dental 60629"}'
```

Wire Twilio sandbox or Meta Cloud API to `/webhooks/whatsapp/twilio` or `/webhooks/whatsapp/meta` (use ngrok locally). Details in [WEEK_PLAN.md](WEEK_PLAN.md).

## Clinic discovery agent

```bash
python agents/make_sample_form.py
python -m agents.clinic_discovery --fetch --url data/sample_clinic_form.csv
# or set GOOGLE_FORMS_CSV_URL to a published Sheets/Forms CSV
```

Telegram approval flow: see [agents/README.md](agents/README.md).

## Deploy (demo week)

- **Streamlit UI** → [Streamlit Community Cloud](https://streamlit.io/cloud) (free), add secrets there
- **FastAPI / WhatsApp** → Railway or Render (free tier)
- **Vercel**, optional landing page only; do **not** rewrite the app onto Vercel this week

## Week plan & David demo

See [WEEK_PLAN.md](WEEK_PLAN.md).
