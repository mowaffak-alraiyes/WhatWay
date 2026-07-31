# BridgeCare — 1-week revitalization plan

Product rename internally: **BridgeCare** (refugee resource finder for Chicago).

## Architecture (keep costs low, ship this week)

| Piece | Where it runs | Why |
|-------|---------------|-----|
| Web UI | **Streamlit** → Streamlit Community Cloud (free) | Already built; polish, don't rewrite |
| WhatsApp + `/search` API | **FastAPI** → Railway / Render free tier | Webhooks need a real HTTP server |
| Future marketing site | Optional **Vercel** (Next.js) later | Vercel is *not* for Streamlit. Don't rewrite the app onto Vercel this week. |

```
WhatsApp (Twilio or Meta) ──► FastAPI /webhooks/whatsapp/*
                              │
Streamlit chat ───────────────┼──► core.pipeline.search_resources()
                              │         ├── data/*.json
                              │         └── Ollama (local llama3, free)
Clinic agent ── Google Forms CSV ──► data/proposed_clinics.json
```

**Do not** rebuild as a Next.js app on Vercel before the David demo — that burns the week. Ship Streamlit + FastAPI; put a one-page Vercel landing in front later if needed.

## Day-by-day (this week)

1. **Today** — Secrets + AI online + smoke test `dental 60629` + WhatsApp simulate endpoint
2. **Day 2** — Twilio sandbox OR Meta test number wired via ngrok → same reply path
3. **Day 3** — Language toggle polish (static i18n + LLM reply translate)
4. **Day 4** — Clinic discovery: publish Forms/Sheets CSV → `python -m agents.clinic_discovery --fetch`
5. **Day 5** — UI pass, deploy Streamlit Cloud + Railway API, dry-run David demo script
6. **Buffer** — Bugfix, Refugee One recruitment notes, push repo

## Secrets you must add (I cannot invent these)

1. Copy `.env.example` → `.env`
2. Start Ollama: `ollama serve` and `ollama pull llama3`
3. (Optional) Neon → only if you want login/comments; search works without it
4. (WhatsApp) Twilio sandbox is fastest for demo: https://console.twilio.com
5. Run `./run_app.sh` and confirm sidebar says AI online

Also copy into `.streamlit/secrets.toml` (or let `run_app.sh` generate it).

## Smoke tests

```bash
# Shared pipeline (no UI)
python -c "from core.pipeline import search_resources; r=search_resources('dental 60629', category='Healthcare', use_llm=False); print(r['text'][:500])"

# WhatsApp simulate
uvicorn api.main:app --port 8000
curl -s -X POST localhost:8000/webhooks/whatsapp/simulate \
  -H 'content-type: application/json' \
  -d '{"from":"test","body":"dental 60629"}' | python -m json.tool
```

## David demo script (~5 min)

1. Open Streamlit → switch language to Español → ask for dental near 60629
2. Show AI online + Alivio / local dental hit
3. Send same query on WhatsApp sandbox → identical results
4. Show `data/proposed_clinics.json` from clinic agent (or dry-run with sample CSV)
5. Mention Refugee One can help clients install / text the WhatsApp number

## Cost control

- AI is **local Ollama only** (no OpenRouter / cloud LLM bill)
- Static UI i18n — no LLM call for labels
- LLM only for intent + short reply + optional translate
- Neon optional
- Twilio sandbox free for spike; Meta Cloud API has free tier for testing
