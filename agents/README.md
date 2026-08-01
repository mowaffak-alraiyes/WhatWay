# Aidr Clinic Ops (Telegram approval → GitHub)

Borrow David’s [local-ai-agents](https://github.com/DrDavidL/local-ai-agents) patterns:
controlled tools, local Ollama summaries, Telegram **polling** (no open ports),
human approval before any GitHub write.

## What it does

1. Ingest form CSV (`GOOGLE_FORMS_CSV_URL`) → verify against GitHub resource lists  
2. **Enrich missing phones/websites** (`enrich_contacts`) from free sources only  
3. Stage **new clinics** or **phone/website/hours updates** in `data/pending_ops.json`  
4. Text you on Telegram to `approve op_…` / `reject op_…`  
5. After approve, `apply op_…` commits to [refugee-resources](https://github.com/mowaffak-alraiyes/refugee-resources) **and refreshes local `data/*.json`**

Scope: `CITY_SCOPE=chicago` (default) or `national`.

## Setup

```bash
# .env
TELEGRAM_BOT_TOKEN=...          # from @BotFather
TELEGRAM_ALLOWED_CHAT_IDS=...   # your numeric chat id
CITY_SCOPE=chicago              # or national
GOOGLE_FORMS_CSV_URL=...        # published Sheet CSV (optional)
GITHUB_TOKEN=...                # or rely on git credential helper
OLLAMA_MODEL=llama3             # free local verify / summaries
```

Start Ollama once:

```bash
ollama serve
ollama pull llama3
```

Message your bot once, then:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

## Import HRSA / Ryan White Excel → GitHub

```bash
python -m agents.import_hrsa_xlsx \
  --health-centers "~/Downloads/Health Centers July 31 2026.xlsx" \
  --hab "~/Downloads/HAB July 31 2026.xlsx" \
  --states IL \
  --push --refresh-local
```

- **Adds** new IL clinics; **updates** blank phone/website only — never strips languages/hours/services  
- HAB rows get **Ryan White HIV/AIDS Program (HRSA HAB)** notes + service context (shown as chips + detail callout)  
- Default `--states IL` (pass `ALL` or `IL,IN,WI` to widen)

Agreed safety model: **read GitHub → propose only → you approve → apply**. Never auto-push. No paid Places API; no bulk Google/Yelp scrape.

```bash
# See what's blank
python -m agents.enrich_contacts --list-gaps

# Stage fills from org sites already listed + optional HRSA CSV
# Download “Health Center Service Delivery Sites” CSV from:
# https://data.hrsa.gov/data/download?hmpgtitle=hmpg-hrsa-data
# Filter to IL / 60xxx and save as data/hrsa_il.csv
python -m agents.enrich_contacts --scan --category healthcare --hrsa data/hrsa_il.csv --limit 20

# Optional: also try DuckDuckGo HTML to find a missing official site (still not Google/Yelp)
python -m agents.enrich_contacts --scan --discover-sites --limit 5

# Missing websites only (best for filling 🔗 Website not listed)
python -m agents.enrich_contacts --scan --websites-only --discover-sites --limit 20

# Your contacts sheet as a local CSV export
python -m agents.enrich_contacts --scan --sheet-file ~/Downloads/contacts.csv --limit 30
```

Ollama (if running) answers “does this phone match this clinic?” before staging. If Ollama is down, proposals still stage marked `unchecked` for your review.

Then the usual gate:

```bash
python -m agents.clinic_ops --list
python -m agents.clinic_ops --notify          # Telegram cards
python -m agents.clinic_ops --approve op_ab12
python -m agents.clinic_ops --apply op_ab12   # GitHub push + refresh data/healthcare.json
python -m agents.clinic_ops --apply op_ab12 --dry-run
```

Or poll Telegram:

```bash
python -m agents.clinic_ops --poll --poll-seconds 0
# reply: approve op_… / reject op_… / apply op_…
```

**Limits:** not every clinic publishes a phone; blanks stay blank. Auto-fill without review invents/wrong-matches — keep human approve.

## Form ingest / new clinics

```bash
CITY_SCOPE=chicago python -m agents.clinic_ops --run
python -m agents.clinic_ops --list
python -m agents.clinic_ops --notify
python -m agents.clinic_ops --approve op_ab12cd
python -m agents.clinic_ops --apply op_ab12cd
```

## Telegram replies

- `list`
- `approve op_ab12cd`
- `reject op_ab12cd`
- `apply op_ab12cd`  ← only after approve; pushes to GitHub + refreshes local JSON

**Mobile queue:** approve on Telegram, then drain all approved in one Terminal command:

```bash
python -m agents.clinic_ops --apply-all --dry-run   # preview
python -m agents.clinic_ops --apply-all              # push all approved
```

## Safety

- LLM never pushes. Only `approve` + `apply` (you) do.
- Only chats in `TELEGRAM_ALLOWED_CHAT_IDS` can command the bot.
- Empty allowlist = **fail closed** (no chat can approve/apply).
- Drafts omit map-pin emoji so Maps geocoding stays clean.
- Enrichment sources: org site, HRSA-style CSV, your sheet — not paid Places.
