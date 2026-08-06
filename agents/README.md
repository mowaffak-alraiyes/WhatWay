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

Scope: `CITY_SCOPE=chicago` (default) or `national`. Active GitHub folder: `RESOURCES_STATE=IL` → `resources/IL/…` (also `CO`, `CA`, …).

## Setup

```bash
# .env
TELEGRAM_BOT_TOKEN=...          # from @BotFather
TELEGRAM_ALLOWED_CHAT_IDS=...   # your numeric chat id
CITY_SCOPE=chicago              # or national
RESOURCES_STATE=IL              # resources/{STATE}/ on GitHub (default IL)
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

## Import HRSA / Ryan White Excel → per-state GitHub

Listings live under **`resources/{STATE}/healthcare.txt`** in [refugee-resources](https://github.com/mowaffak-alraiyes/refugee-resources/tree/main/resources).
Download Health Centers (+ optional HAB) Excel from [HRSA data download](https://data.hrsa.gov/data/download) (same data that powers [Find a Health Center](https://findahealthcenter.hrsa.gov/)).

Hubs (250-mile default): **IL** Chicago · **CO** Denver · **CA** San Francisco, Los Angeles, Sacramento.

```bash
# Stage CO/CA/IL diffs → Telegram digest per state + ❤ cards
python -m agents.import_hrsa_xlsx \
  --health-centers "~/Downloads/Health Centers.xlsx" \
  --hab "~/Downloads/HAB.xlsx" \
  --states IL,CO,CA \
  --hub-radius-miles 250 \
  --stage-ops --notify-telegram

# Or push IL fills directly (known-safe blank phone/website only)
python -m agents.import_hrsa_xlsx \
  --health-centers "~/Downloads/Health Centers.xlsx" \
  --hab "~/Downloads/HAB.xlsx" \
  --states IL \
  --push --refresh-local
```

- **Adds** new clinics; **updates** blank phone/website only — never strips languages/hours/services  
- HAB rows get **Ryan White HIV/AIDS Program (HRSA HAB)** notes + service context  
- Telegram sends one **📍 STATE** digest, then individual cards (`❤` approve+apply / `👎` reject)  
- Apply writes to `resources/{state}/healthcare.txt` using each op’s `state` field

### Auto-fetch from Find a Health Center (no manual download)

Same backend as [findahealthcenter.hrsa.gov](https://findahealthcenter.hrsa.gov/) (`HDWLocatorApi/healthcenters/find`). For each state the agent queries **hub + surrounding cities** at 250 miles, **dedupes** overlapping sites, writes XLSX, then can stage/Telegram:

```bash
# IL surrounding: Chicago, Aurora, Joliet, Naperville, Rockford, Peoria, Springfield
python -m agents.fetch_hrsa_finder \
  --states IL,CO,CA \
  --radius 250 \
  --out-dir data/hrsa_finder \
  --stage-ops --notify-telegram
```

Fetch-only (writes `data/hrsa_finder/health_centers_{ST}.xlsx`):

```bash
python -m agents.fetch_hrsa_finder --states IL --radius 250 --dry-run
```

Agreed safety model: **read GitHub → propose only → you approve → apply**. Never auto-push new states without review. No paid Places API; no bulk Google/Yelp scrape; no brittle browser scraping of the map UI (public locator API instead).

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

**Mobile queue:** approve on Telegram, then drain:

```bash
python -m agents.clinic_ops --apply-all --dry-run   # preview
python -m agents.clinic_ops --apply-all              # push all approved
```

Or from Telegram after a batch (e.g. Indiana):

```
approve all IN
```

Aliases: `approve-apply all`, `approve all`, `apply all` (optional state code).

## Education & resettlement (not just healthcare)

```bash
# Stage NEW Chicago education + legal/shelter orgs (Ollama verifies; you still approve)
CITY_SCOPE=chicago python -m agents.clinic_ops --discover-new --limit 15
# or: python -m agents.discover_new --category education --category resettlement

# Fill missing phones/websites on existing education / resettlement listings
CITY_SCOPE=chicago python -m agents.enrich_contacts --scan \
  --category education --category resettlement --discover-sites --limit 20

python -m agents.clinic_ops --list
python -m agents.clinic_ops --notify   # Telegram cards include Category:
```

Form CSV ingest can set a `Category` column (`education` / `resettlement` / `healthcare`); otherwise NEW form rows default to healthcare.

## Overnight worker (free sources)

Runs enrich (phone/website/languages/services/hours) + education/resettlement discovery + Reddit JSON, then texts you on Telegram.

```bash
# Keep Telegram poll running in one terminal:
python -m agents.clinic_ops --poll --poll-seconds 0

# Overnight finder in another:
python -m agents.overnight_ops --interval-min 60
# or one cycle: python -m agents.overnight_ops --once
```

Approve with ❤ / reject with 👎 on each card (text commands still work).
❤ also **applies to GitHub** immediately (`AIDR_AUTO_APPLY_ON_HEART=1`).

### Confidence tiers
| Tier | Behavior |
|------|----------|
| **high** + known source (org site / HRSA / curated seed) | Auto-apply overnight (`AIDR_AUTO_APPLY_HIGH=1`) |
| **medium** | Telegram asks for ❤ → approve+apply |
| **low** / Reddit-only | Ask for ❤ (or skip if `AIDR_SKIP_LOW_CONFIDENCE=1`) |

## Safety

- LLM never pushes on its own for medium/low — you ❤ or overnight high-tier does.
- Only chats in `TELEGRAM_ALLOWED_CHAT_IDS` can command the bot.
- Empty allowlist = **fail closed** (no chat can approve/apply).
- Drafts omit map-pin emoji so Maps geocoding stays clean.
- Enrichment sources: org site, HRSA-style CSV, your sheet, Reddit public JSON — not paid Places.
