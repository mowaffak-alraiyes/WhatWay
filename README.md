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

## WhatsApp API (spike)

```bash
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

## Deploy (demo week)

- **Streamlit UI** → [Streamlit Community Cloud](https://streamlit.io/cloud) (free) — add secrets there
- **FastAPI / WhatsApp** → Railway or Render (free tier)
- **Vercel** — optional landing page only; do **not** rewrite the app onto Vercel this week

## Week plan & David demo

See [WEEK_PLAN.md](WEEK_PLAN.md).
