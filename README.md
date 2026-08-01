# Aidr — Refugee Resource Assistant

Find healthcare, education, and legal/shelter resources for refugee families in Chicago — via web chat or WhatsApp.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Ensure Ollama is running: ollama serve && ollama pull llama3
./run_app.sh
```

Open http://localhost:8501 — try **Healthcare → dental 60629**.

## Setup and security checklist

1. Put secrets only in `.env` / `.streamlit/secrets.toml` — never commit them (both are gitignored).
2. Set `ADMIN_PASSWORD` before using the Streamlit admin page (no default password).
3. Set `TELEGRAM_ALLOWED_CHAT_IDS` for clinic ops; an empty allowlist rejects all Telegram commands.
4. WhatsApp dry-run logs mask phone numbers; conversation sessions key on hashed IDs.
5. SQL uses parameterized queries (`%s` + tuple). Do not interpolate user input into SQL.
6. FastAPI CORS defaults to localhost Streamlit; set `AIDR_CORS_ORIGINS` for deploy.
7. `/webhooks/whatsapp/simulate` is off unless `AIDR_ENABLE_SIMULATE=1`.
8. When `TWILIO_AUTH_TOKEN` is set, Twilio webhooks require a valid `X-Twilio-Signature`.

**Privacy:** We do not intend to store raw phone numbers or IPs in logs. Prefer hashed identifiers. Resource data is public clinic listings, not patient records.

## WhatsApp API (spike)

```bash
export AIDR_ENABLE_SIMULATE=1   # local smoke test only
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

- **Streamlit UI** → [Streamlit Community Cloud](https://streamlit.io/cloud) (free) — add secrets there
- **FastAPI / WhatsApp** → Railway or Render (free tier)
- **Vercel** — optional landing page only; do **not** rewrite the app onto Vercel this week

## Week plan & David demo

See [WEEK_PLAN.md](WEEK_PLAN.md).
