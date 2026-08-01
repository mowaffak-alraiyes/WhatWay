import streamlit as st
import requests
import re
import uuid
import database as db
from typing import List, Dict, Tuple, Optional
import search_helpers
import search
import data_loader
import neighborhood_mapping
import auth
import llm_service

# ===========================
# Page & Styles
# ===========================
st.set_page_config(
    page_title="Aidr",
    page_icon="🟩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
db.initialize_database()

# Initialize authentication
auth.init_session_state()

import core.i18n as i18n

# Language must bind BEFORE hero/Pip (widget key is available on the same rerun).
_LANG_CODES = ["en", "es", "ar", "fr", "pl", "zh", "ur", "hi", "uk", "sw"]
if "ui_lang_code" not in st.session_state:
    # Migrate older English-name session values once
    _legacy = st.session_state.get("response_language") or st.session_state.get("preferred_language")
    st.session_state["ui_lang_code"] = i18n.normalize_lang(_legacy) if _legacy else "en"
if st.session_state["ui_lang_code"] not in _LANG_CODES:
    st.session_state["ui_lang_code"] = "en"

# Language widget runs in the sidebar *before* hero so copy updates same-run
with st.sidebar:
    _label_lang = st.session_state["ui_lang_code"]
    st.markdown(
        f'<p class="aidr-side-title">{i18n.t("language_label", _label_lang)}</p>',
        unsafe_allow_html=True,
    )
    _ui_lang0 = st.selectbox(
        i18n.t("language_label", _label_lang),
        options=_LANG_CODES,
        format_func=lambda c: i18n.LANGUAGES.get(c, c),
        key="ui_lang_code",
        label_visibility="collapsed",
    )
    st.session_state["preferred_language"] = i18n.CODE_TO_NAME.get(_ui_lang0, "English")
    st.session_state["response_language"] = st.session_state["preferred_language"]
    st.markdown('<hr class="aidr-side-rule"/>', unsafe_allow_html=True)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

/* App text — do NOT override Material Icons (fixes keyboard_double_arrow text) */
.stApp, .stMarkdown, .stButton > button, .stSelectbox, .stTextInput,
div[data-testid="stChatMessage"], section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
.bc-hero, .bc-brand, .bc-tag, .pip-wrap, .pip-bubble {{
  font-family: 'DM Sans', system-ui, -apple-system, sans-serif !important;
}}
/* Keep Streamlit / Material icon font intact */
span[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"],
.material-icons,
.material-symbols-rounded,
.material-symbols-outlined {{
  font-family: "Material Symbols Rounded", "Material Icons", sans-serif !important;
  font-style: normal !important;
  font-weight: normal !important;
  letter-spacing: normal !important;
}}

.stApp {{
  background:
    radial-gradient(900px 420px at 0% -5%, #d4efe4 0%, transparent 55%),
    radial-gradient(700px 360px at 100% 0%, #e8f5ef 0%, transparent 50%),
    #F4F7F5;
}}
/* Wider main column — Streamlit default feels too narrow for listings */
.main .block-container {{
  max-width: 1180px !important;
  padding-top: 1.25rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
}}
section[data-testid="stMain"] > div {{
  max-width: none;
}}
.bc-hero {{
  background: linear-gradient(135deg, #4EB086 0%, #3d9a72 100%);
  border-radius: 18px;
  padding: 1.1rem 1.35rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 8px 24px rgba(78, 176, 134, 0.28);
  color: white;
}}
.bc-brand {{
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  line-height: 1.1;
  color: #fff !important;
  letter-spacing: -0.03em;
}}
.bc-tag {{
  margin: 0.4rem 0 0 0;
  color: rgba(255,255,255,0.92);
  font-size: 0.98rem;
  max-width: 42rem;
  font-weight: 450;
}}
section[data-testid="stSidebar"] {{
  background: #ffffff;
  border-right: 1px solid rgba(78,176,134,0.18);
}}
section[data-testid="stSidebar"] > div {{
  padding-top: 0.75rem;
}}
/* Even sidebar rhythm */
.aidr-side-block {{
  margin: 0 0 1.15rem 0;
  padding: 0;
}}
.aidr-side-block h3, .aidr-side-title {{
  font-size: 0.78rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #5a7368 !important;
  margin: 0 0 0.45rem 0 !important;
}}
.aidr-side-block .stCaption, .aidr-side-cap {{
  margin-top: 0 !important;
  margin-bottom: 0.55rem !important;
  color: #6b8178 !important;
  font-size: 0.82rem !important;
  line-height: 1.35;
}}
.aidr-side-rule {{
  border: none;
  border-top: 1px solid rgba(78,176,134,0.18);
  margin: 0.15rem 0 1.15rem 0;
}}
div[data-testid="stChatMessage"] {{
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(78,176,134,0.15);
  padding: 0.35rem 0.5rem;
  box-shadow: 0 2px 8px rgba(26,46,40,0.04);
}}
.stButton > button {{
  border-radius: 999px !important;
  font-weight: 600 !important;
}}
.stButton > button[kind="secondary"] {{
  border: 1.5px solid #4EB086 !important;
  color: #1a2e28 !important;
  background: #fff !important;
}}
.stButton > button[kind="primary"] {{
  background: #4EB086 !important;
}}
section[data-testid="stSidebar"] .stLinkButton > a,
section[data-testid="stSidebar"] a[data-testid="stBaseLinkButton"] {{
  border-radius: 10px !important;
}}
.aidr-card {{
  margin: 0.55rem 0 0.2rem 0;
  padding: 0.55rem 0.7rem 0.15rem 0.7rem;
  border-left: 3px solid #4EB086;
  background: rgba(255,255,255,0.72);
  border-radius: 0 10px 10px 0;
}}
.aidr-card-title {{
  margin: 0 0 0.25rem 0 !important;
  font-size: 1.02rem;
  color: #1a2e28;
  line-height: 1.3;
}}
div[data-testid="stChatMessage"] {{
  border-radius: 14px !important;
}}
/* Hide Streamlit default robot when Pip bubble / Yelp cards are present */
div[data-testid="stChatMessage"]:has(.pip-chat) [data-testid="stChatMessageAvatar"],
div[data-testid="stChatMessage"]:has(.pip-chat) [data-testid="stChatAvatarIcon-assistant"],
div[data-testid="stChatMessage"]:has(.pip-chat) img[alt="assistant avatar"],
div[data-testid="stChatMessage"]:has(.yelp-card) [data-testid="stChatMessageAvatar"],
div[data-testid="stChatMessage"]:has(.yelp-card) [data-testid="stChatAvatarIcon-assistant"],
div[data-testid="stChatMessage"]:has(.yelp-card) img[alt="assistant avatar"] {{
  display: none !important;
}}
div[data-testid="stChatMessage"]:has(.pip-chat),
div[data-testid="stChatMessage"]:has(.yelp-card) {{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding-left: 0 !important;
}}
/* Sticky category bar — only the keyed container (NOT :has(), which
   matched parent blocks and covered the page, eating the first click). */
div.st-key-aidr_cat_bar {{
  position: sticky !important;
  top: 0 !important;
  z-index: 120 !important;
  background: rgba(244, 247, 245, 0.96) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 0.55rem 0.35rem 0.65rem 0.35rem !important;
  margin: 0 0 0.35rem 0 !important;
  border-bottom: 1px solid rgba(78,176,134,0.22);
  box-shadow: 0 6px 16px rgba(26,46,40,0.06);
}}
/* Yelp card action row — equal-height pills */
div[data-testid="stHorizontalBlock"] .stButton > button {{
  white-space: nowrap !important;
}}
/* Room for ChatGPT-style prompt rail on the right */
.main .block-container {{
  padding-right: 3.25rem !important;
}}
.aidr-prompt-anchor {{
  height: 0;
  width: 0;
  overflow: hidden;
  scroll-margin-top: 96px;
}}
</style>
<div class="bc-hero">
  <p class="bc-brand">{i18n.t("brand", _ui_lang0)}</p>
  <p class="bc-tag">{i18n.t("tagline", _ui_lang0)}</p>
</div>
""", unsafe_allow_html=True)

import core.mascot as mascot
mascot.render_pip(
    lang=_ui_lang0,
    greeting=i18n.t("bot_hello", _ui_lang0),
    ask_prefix=i18n.t("ask_prefix", _ui_lang0),
    phrases=i18n.ask_phrases(_ui_lang0),
)


# ===========================
# Constants
# ===========================
TOP_N = 3  # show first N; user can type "more" to fetch next batch

# QR Code functionality removed - not necessary

import core.spellcheck as spellcheck

DATA_SOURCES = {
    "Healthcare": [
        "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/healthcare.txt",
        "/mnt/data/Healthcare Resources.txt",
    ],
    "Education": [
        "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/education.txt",
        "/mnt/data/Education Resources.txt",
        "/mnt/data/Education Resources (1).txt",
    ],
    "Resettlement / Legal / Shelter": [
        "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/ResettlementLegalShelterBasicNeeds.txt",
        "/mnt/data/Resettlement Legal Shelter Needs.txt",
        "/mnt/data/Resettlement Legal Shelter Needs (1).txt",
    ],
}

BASE_SYNONYMS = {
    "common": {
        "bilingual": {"bilingual","spanish","mandarin","arabic","polish","urdu","cantonese","taiwanese","hindi","yoruba","kannada","tamil","french","swahili","tigrinya","ukrainian"},
        "hours": {"hours","open","closing","time","times","schedule"},
        "address": {"address","where","location"},
        "phone": {"phone","number","call","contact"},
        "website": {"website","site","link"},
    },
    "Healthcare": {
        "dental": {"dental","dentist","teeth","tooth","oral","mouth"},
        "pediatric": {"pediatric","pediatrics","children","child","kid","kids","adolescent","youth"},
        "women": {"women","woman","female","obgyn","ob/gyn","ob-gyn","ob gyn","prenatal","midwifery","obstetrics","gynecology"},
        "mental": {"behavioral","mental","counseling","counselor","therapy","therapist","psychiatry","psychiatric"},
        "primary": {"primary","family","internal medicine","family medicine","adult"},
        "immunization": {"immunization","immunizations","vaccination","vaccinations","shots","vaccine","vaccines"},
    },
    "Education": {
        "esl": {"esl","english","language","tutoring","classes","citizenship","ged","literacy","after-school","after school","youth"},
    },
    "Resettlement / Legal / Shelter": {
        "legal": {"legal","law","attorney","immigration","asylum","daca","family reunification"},
        "shelter": {"shelter","housing","emergency","homeless"},
        "benefits": {"benefits","snap","medicaid","cash assistance","311","food","pantry"},
        "resettlement": {"resettlement","case management","employment","job readiness","welcoming center"},
    },
}

# ===========================
# Utilities
# ===========================
def fetch_text_from_sources(sources: List[str]) -> str:
    last_err = None
    for src in sources:
        try:
            if src.startswith("http"):
                r = requests.get(src, timeout=20)
                r.raise_for_status()
                if r.text.strip():
                    return r.text
            else:
                with open(src, "r", encoding="utf-8") as f:
                    text = f.read()
                    if text.strip():
                        return text
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Failed to load dataset from any source. Last error: {last_err}")

def first_match(pat: str, text: str) -> str:
    m = re.search(pat, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else ""

def parse_blocks(resource_text: str) -> List[Dict]:
    # Split each numbered block "NN. Name"
    blocks = re.split(r"\n(?=\d+\.\s)|\A(?=\d+\.\s)", resource_text.strip())
    out = []
    for blk in blocks:
        if not blk.strip():
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.+)", blk.strip(), flags=re.MULTILINE)
        if m:
            item_id = m.group(1).strip()
            name = m.group(2).strip()
        else:
            first_line = blk.strip().splitlines()[0].strip()
            item_id = str(len(out) + 1)
            name = re.sub(r"^\s*\d+\.\s*", "", first_line)

        address   = first_match(r"📍\s*(.+)", blk)
        website   = first_match(r"🌐\s*(https?://\S+)", blk)
        languages = first_match(r"🗣\s*Languages:\s*(.+)", blk)
        # Multiple emoji fallbacks for Services
        services  = (first_match(r"(?:🏥|🛟|🛠️|🧰)\s*Services:\s*(.+)", blk) or 
                    first_match(r"Services:\s*(.+)", blk))
        # Multiple fallbacks for Hours
        hours     = (first_match(r"⏰\s*Hours:\s*(.+)", blk) or 
                    first_match(r"Hours:\s*(.+)", blk))
        # Multiple fallbacks for Phone
        phone     = (first_match(r"📞\s*(.+)", blk) or 
                    first_match(r"Phone:\s*(.+)", blk) or
                    first_match(r"📞\s*Phone:\s*(.+)", blk))
        # Search for zip in full block if address is missing
        zip_code  = first_match(r"\b(60\d{3})\b", address or blk)

        out.append({
            "id": item_id,
            "name": name,
            "address": address,
            "zip": zip_code,
            "website": website,
            "languages": languages,
            "services": services,
            "hours": hours,
            "phone": phone,
            "_search_blob": " ".join([name or "", address or "", languages or "", services or ""]).lower(),
        })
    return out

def _synonym_vocab_extras() -> Tuple[str, ...]:
    extras = set()
    for group in BASE_SYNONYMS.values():
        if isinstance(group, dict):
            for key, syns in group.items():
                extras.add(str(key).lower())
                extras.update(str(s).lower() for s in syns)
    return tuple(sorted(extras))


def detect_misspellings(query: str) -> List[Tuple[str, str]]:
    """Fuzzy spelling fixes against domain vocab (not a hard-coded typo list)."""
    result = spellcheck.check_query(query or "")
    return list(result.get("fixes") or [])


def _seed_spell_vocab(items: Optional[List[dict]] = None) -> None:
    syn = _synonym_vocab_extras()
    spellcheck.build_vocabulary.cache_clear()
    if items:
        spellcheck.refresh_vocabulary_from_items(items, extra=syn)
    else:
        spellcheck.build_vocabulary(syn)

def detect_zip_from_query(query: str, known_zips: List[str] = None) -> str:
    """
    Detect ZIP from query. Exact 60xxx first; otherwise fuzzy-resolve
    any 4–5 digit token against known dataset ZIPs (typo-tolerant, no typo list).
    """
    known = known_zips or []

    # Exact Chicago-area ZIP
    zip_match = re.search(r"\b(60\d{3})\b", query or "")
    if zip_match:
        raw = zip_match.group(1)
        if known:
            resolved, score = neighborhood_mapping.resolve_zip_against_known(raw, known)
            return resolved or raw
        return raw

    # Any 4–5 digit run — resolve via similarity to known ZIPs (handles typos)
    digit_match = re.search(r"\b(\d{4,5})\b", query or "")
    if digit_match and known:
        resolved, score = neighborhood_mapping.resolve_zip_against_known(digit_match.group(1), known)
        if resolved:
            return resolved

    # Neighborhood name → first ZIP in that cluster
    _cleaned, zips = neighborhood_mapping.expand_neighborhood_query(query or "")
    if zips:
        if known:
            for z in zips:
                if z in known:
                    return z
        return zips[0]

    return None


def clean_query_of_zip(query: str) -> str:
    """Remove ZIP-like digit tokens from query text to avoid double-counting."""
    cleaned = re.sub(r"\b(60\d{3})\b", "", query or "")
    cleaned = re.sub(r"\b(\d{4,5})\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def detect_service_from_query(query: str, category: str) -> str:
    """Auto-detect service type from search query and return it if found."""
    query_lower = query.lower()
    
    # Healthcare services
    if category == "Healthcare":
        if any(word in query_lower for word in ["dental", "dentist", "teeth", "tooth", "oral"]):
            return "dental"
        elif any(word in query_lower for word in ["pediatric", "children", "child", "kid", "kids", "youth"]):
            return "pediatric"
        elif any(word in query_lower for word in ["mental", "counseling", "therapy", "psychiatry"]):
            return "mental health"
        elif any(word in query_lower for word in ["women", "obgyn", "prenatal", "midwifery"]):
            return "women's health"
        elif any(word in query_lower for word in ["immunization", "vaccination", "shots", "vaccine"]):
            return "immunization"
    
    # Education services
    elif category == "Education":
        if any(word in query_lower for word in ["esl", "english", "language", "tutoring", "classes"]):
            return "ESL"
        elif any(word in query_lower for word in ["ged", "citizenship", "literacy"]):
            return "GED/Citizenship"
        elif any(word in query_lower for word in ["after-school", "after school", "youth"]):
            return "Youth Programs"
    
    # Legal/Shelter services
    elif category == "Resettlement / Legal / Shelter":
        if any(word in query_lower for word in ["legal", "law", "attorney", "immigration", "asylum", "daca"]):
            return "Legal Services"
        elif any(word in query_lower for word in ["shelter", "housing", "emergency", "homeless"]):
            return "Shelter/Housing"
        elif any(word in query_lower for word in ["benefits", "snap", "medicaid", "cash assistance"]):
            return "Benefits Assistance"
        elif any(word in query_lower for word in ["resettlement", "case management", "employment", "job"]):
            return "Resettlement Services"
    
    return None

def detect_day_from_query(query: str) -> str:
    """Auto-detect day of week from search query and return it if found."""
    query_lower = query.lower()
    
    days = {
        "monday": "Monday", "mon": "Monday",
        "tuesday": "Tuesday", "tue": "Tuesday", "tues": "Tuesday",
        "wednesday": "Wednesday", "wed": "Wednesday",
        "thursday": "Thursday", "thu": "Thursday", "thurs": "Thursday",
        "friday": "Friday", "fri": "Friday",
        "saturday": "Saturday", "sat": "Saturday",
        "sunday": "Sunday", "sun": "Sunday"
    }
    
    for day_key, day_value in days.items():
        if day_key in query_lower:
            return day_value
    
    return None

# QR code generation function removed - not necessary

def parse_day_ranges(hours_input) -> List[str]:
    """
    Parse day ranges from hours data.
    Handles both structured dict format (from JSON) and string format (from .txt files).
    """
    available_days = []
    
    # Handle structured dict format (from JSON files)
    if isinstance(hours_input, dict):
        day_map = {
            "monday": "Monday",
            "tuesday": "Tuesday", 
            "wednesday": "Wednesday",
            "thursday": "Thursday",
            "friday": "Friday",
            "saturday": "Saturday",
            "sunday": "Sunday"
        }
        for day_key, day_value in day_map.items():
            if day_key in hours_input and hours_input[day_key]:
                available_days.append(day_value)
        return available_days
    
    # Handle string format (from .txt files or hours_text)
    if not isinstance(hours_input, str):
        return []
    
    hours_lower = hours_input.lower()
    
    # Day mapping for abbreviations
    day_map = {
        "mon": "Monday", "tue": "Tuesday", "tues": "Tuesday", "wed": "Wednesday",
        "thu": "Thursday", "thurs": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"
    }
    
    # Look for day ranges like "Mon-Thu" or "Mon - Thu"
    range_pattern = r'\b(mon|tue|tues|wed|thu|thurs|fri|sat|sun)\s*[-–]\s*(mon|tue|tues|wed|thu|thurs|fri|sat|sun)\b'
    range_matches = re.findall(range_pattern, hours_lower)
    
    for start_day, end_day in range_matches:
        start_idx = list(day_map.keys()).index(start_day)
        end_idx = list(day_map.keys()).index(end_day)
        
        # Handle wrapping around (e.g., Fri-Mon)
        if start_idx <= end_idx:
            day_range = list(day_map.keys())[start_idx:end_idx + 1]
        else:
            day_range = list(day_map.keys())[start_idx:] + list(day_map.keys())[:end_idx + 1]
        
        for day in day_range:
            available_days.append(day_map[day])
    
    # Look for individual days or comma-separated lists
    individual_pattern = r'\b(mon|tue|tues|wed|thu|thurs|fri|sat|sun)\b'
    individual_matches = re.findall(individual_pattern, hours_lower)
    
    for day in individual_matches:
        if day_map[day] not in available_days:  # Avoid duplicates
            available_days.append(day_map[day])
    
    # Look for full day names
    full_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for full_day in full_days:
        if full_day in hours_lower and full_day.capitalize() not in available_days:
            available_days.append(full_day.capitalize())
    
    return available_days

def is_day_available_in_dataset(day: str, items: List[Dict]) -> bool:
    """Check if a specific day is actually available in the dataset."""
    if not day or day == "All":
        return False
    
    day_lower = day.lower()
    for item in items:
        # Try hours_text first (from .txt), then structured hours
        hours = item.get("hours_text") or item.get("hours") or ""
        if hours:
            # Use the smart parsing to get all available days (handles both dict and string)
            available_days = parse_day_ranges(hours)
            # Check if the requested day is in the available days
            if day in available_days:
                return True
    
    return False

def clean_query_of_service_and_day(query: str, detected_service: str = None, detected_day: str = None) -> str:
    """Remove detected service and day from query text to avoid double-counting in search."""
    cleaned = query
    
    if detected_service:
        # Remove service-related words
        service_words = detected_service.lower().split()
        for word in service_words:
            cleaned = re.sub(rf'\b{re.escape(word)}\b', '', cleaned, flags=re.IGNORECASE)
    
    if detected_day:
        # Remove day-related words
        day_words = detected_day.lower().split()
        for word in day_words:
            cleaned = re.sub(rf'\b{re.escape(word)}\b', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def expand_terms(query: str, category: str) -> List[str]:
    q = (query or "").lower()
    stop = {
        "find", "need", "want", "looking", "for", "near", "in", "at", "the", "a", "an",
        "help", "me", "please", "some", "any", "get", "with", "and", "or", "to", "of",
        "my", "i", "im", "is", "are", "clinic", "clinics", "place", "places",
    }
    words = {w for w in re.findall(r"[a-zA-Z0-9]+", q) if w not in stop and len(w) > 1}
    expanded = set(words)

    cat_syns = {}
    cat_syns.update(BASE_SYNONYMS.get("common", {}))
    cat_syns.update(BASE_SYNONYMS.get(category, {}))
    for key, syns in cat_syns.items():
        if (key in words) or (words & syns):
            expanded |= syns
            expanded.add(key)
    return sorted(expanded)


def must_have_patterns(terms: List[str], category: str) -> List[re.Pattern]:
    """Preferred service cues — used as soft boosts, not hard gates."""
    pats = []
    t = set(terms)
    if category == "Healthcare":
        if {"dental", "dentist", "oral", "tooth", "teeth"} & t:
            pats.append(re.compile(r"\b(dental|dentist|oral|tooth|teeth)\b", re.I))
        if {"pediatric", "children", "youth", "adolescent", "kid", "kids"} & t:
            pats.append(re.compile(r"\b(pediatric|children|youth|adolescent|kid|kids)\b", re.I))
        if {"mental", "therapy", "counseling", "psychiatric", "behavioral"} & t:
            pats.append(re.compile(r"\b(mental|therapy|counseling|psychiatric|behavioral)\b", re.I))
        if {"women", "womens", "prenatal", "obgyn", "gynecology"} & t:
            pats.append(re.compile(r"\b(women|obstetrics|gynecology|prenatal|ob/?gyn)\b", re.I))
    if category == "Resettlement / Legal / Shelter":
        if {"legal", "immigration", "asylum", "daca"} & t:
            pats.append(re.compile(r"\b(legal|immigration|asylum|daca)\b", re.I))
        if {"shelter", "housing", "homeless", "emergency"} & t:
            pats.append(re.compile(r"\b(shelter|housing|emergency)\b", re.I))
    if category == "Education":
        if {"esl", "english", "literacy", "ged", "citizenship"} & t:
            pats.append(re.compile(r"\b(esl|english|literacy|ged|citizenship)\b", re.I))
    return pats


def _norm_service_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _item_matches_service(item: Dict, service_filter: str) -> bool:
    """Lenient service match across list keys, labels, and free text."""
    if not service_filter or service_filter == "All":
        return True
    target = _norm_service_key(service_filter)
    if not target:
        return True
    services = item.get("services") or []
    if isinstance(services, list):
        for s in services:
            if target in _norm_service_key(str(s)) or _norm_service_key(str(s)) in target:
                return True
    else:
        if target in _norm_service_key(str(services)):
            return True
    for field in ("services_text", "search_blob", "subcategories"):
        val = item.get(field) or ""
        if isinstance(val, list):
            val = " ".join(str(x) for x in val)
        if target in _norm_service_key(str(val)):
            return True
        # spaced form e.g. mental health inside blob
        spaced = re.sub(r"_+", " ", service_filter.lower())
        if spaced and spaced in str(val).lower():
            return True
    return False


def _term_hit(term: str, blob: str) -> bool:
    """Substring or prefix hit — leeway for short / partial words."""
    if not term or not blob:
        return False
    if term in blob:
        return True
    if len(term) >= 3:
        return any(w.startswith(term) or term.startswith(w[: max(3, len(term))]) for w in blob.split() if len(w) >= 3)
    return False


def rank_items(
    items: List[Dict],
    query: str,
    category: str,
    zip_filter: str,
    lang_filter: str,
    service_filter: str = "All",
    day_filter: str = "All",
    *,
    soft_filters: bool = True,
) -> List[Tuple[float, Dict]]:
    """
    Lenient ranking: ZIP/lang/service/day/must-have are boosts (or soft penalties),
    not hard gates — so near-misses still surface. Fuzzy score adds typo leeway.
    ZIP: exact > neighborhood/numeric nearby cluster > others.
    """
    from rapidfuzz import fuzz

    terms = expand_terms(query, category)
    require = must_have_patterns(terms, category)
    timing_keywords = ("now", "today", "open", "available", "immediate", "urgent")
    wants_timing = any(kw in (query or "").lower() for kw in timing_keywords)
    q_raw = (query or "").strip().lower()

    # Build ZIP context: resolve typos against dataset, expand nearby cluster
    known_zips = sorted(
        {
            str(c.get("zip_code") or c.get("zip") or "").strip()
            for c in items
            if str(c.get("zip_code") or c.get("zip") or "").strip()
        }
    )
    target_zip = ""
    nearby_zips: List[str] = []
    if zip_filter and zip_filter != "All":
        resolved, _sc = neighborhood_mapping.resolve_zip_against_known(zip_filter, known_zips)
        target_zip = resolved or str(zip_filter).strip()
        nearby_zips = neighborhood_mapping.nearby_zip_cluster(target_zip, known_zips)

    ranked: List[Tuple[float, Dict]] = []
    for c in items:
        blob = c.get("search_blob") or c.get("_search_blob", "")
        if not blob and isinstance(c.get("services"), list):
            blob = " ".join(
                [
                    str(c.get("name", "")),
                    str(c.get("address", "")),
                    " ".join(c.get("services") or []),
                    " ".join(c.get("subcategories") or []),
                    " ".join(c.get("languages") or []),
                    str(c.get("services_text") or ""),
                ]
            ).lower()
        else:
            blob = str(blob).lower()

        if isinstance(c.get("services"), list):
            svc = " ".join(c.get("services") or []).lower() + " " + str(c.get("services_text") or "").lower()
        else:
            svc = str(c.get("services_text") or c.get("services") or "").lower()
        haystack = f"{blob} {svc}"

        item_zip = str(c.get("zip_code") or c.get("zip") or "").strip()
        if not item_zip:
            addr_m = re.search(r"\b(60\d{3})\b", str(c.get("address") or ""))
            if addr_m:
                item_zip = addr_m.group(1)

        # --- Soft / hard filters ---
        zip_tier = "none"
        if target_zip:
            zip_tier = neighborhood_mapping.zip_match_tier(item_zip, target_zip, nearby_zips)
            zip_ok = zip_tier in ("exact", "nearby") or not item_zip
            if not zip_ok and not soft_filters:
                continue
        else:
            zip_ok = True

        lang_ok = True
        if lang_filter and lang_filter != "All":
            item_langs = c.get("languages", [])
            if isinstance(item_langs, list):
                lang_ok = any(lang_filter.lower() in str(lang).lower() for lang in item_langs)
            else:
                lang_ok = lang_filter.lower() in str(item_langs or "").lower()
            if not lang_ok and not soft_filters:
                continue

        service_ok = _item_matches_service(c, service_filter) if service_filter != "All" else True
        if service_filter != "All" and not service_ok and not soft_filters:
            continue

        day_ok = True
        if day_filter != "All":
            hours = c.get("hours_text") or c.get("hours") or ""
            if hours:
                available_days = parse_day_ranges(hours)
                day_ok = day_filter in available_days
            else:
                day_ok = False  # missing hours — still keep in soft mode
            if not day_ok and not soft_filters and hours:
                continue

        must_ok = True
        if require:
            must_ok = all(p.search(haystack) for p in require)
            if not must_ok and not soft_filters:
                continue

        # --- Score ---
        term_hits = sum(1 for t in terms if _term_hit(t, haystack)) if terms else 0
        score = float(term_hits)

        name_l = str(c.get("name") or "").lower()
        name_tokens = set(re.findall(r"[a-z0-9]+", name_l))
        q_tokens = set(re.findall(r"[a-z0-9]+", q_raw))

        # Exact name-token match (e.g. query "SAMS" → "SAMS Free Specialty Clinic")
        if q_tokens and q_tokens.issubset(name_tokens):
            score += 10.0
        elif q_raw and q_raw in name_l:
            score += 8.0

        # Fuzzy leeway — for short queries, score against NAME only (avoid junk hits)
        fuzzy = 0.0
        if q_raw:
            try:
                focus = f"{c.get('name', '')} {svc} {' '.join(c.get('subcategories') or [])}".lower()
                name_focus = name_l
                if len(q_raw) <= 5:
                    fuzzy = max(
                        fuzz.ratio(q_raw, name_focus[: max(len(q_raw) * 3, 12)]),
                        fuzz.token_set_ratio(q_raw, name_focus),
                        fuzz.partial_ratio(q_raw, name_focus) if q_raw in name_focus or any(q_raw == t[:len(q_raw)] for t in name_tokens) else 0,
                    ) / 100.0
                    # Require real name signal for acronyms / short queries
                    if fuzzy < 0.85 and not (q_tokens & name_tokens):
                        fuzzy = 0.0
                else:
                    fuzzy = max(
                        fuzz.partial_ratio(q_raw, focus),
                        fuzz.token_set_ratio(q_raw, focus),
                    ) / 100.0
                score += fuzzy * 4.0
            except Exception:
                pass

        if must_ok and require:
            score += 3.0
        elif require and not must_ok:
            score *= 0.55  # soft penalty, still keep if other signal

        # ZIP: exact best, nearby cluster next (so empty exact ZIP still surfaces locals)
        if target_zip:
            if zip_tier == "exact":
                score += 4.0
                c["_zip_tier"] = "exact"
            elif zip_tier == "nearby":
                score += 2.6
                c["_zip_tier"] = "nearby"
            else:
                score *= 0.72
                c["_zip_tier"] = "far"
        else:
            c["_zip_tier"] = None

        if lang_ok and lang_filter and lang_filter != "All":
            score += 1.5
        if service_ok and service_filter and service_filter != "All":
            score += 2.5
        if day_ok and day_filter and day_filter != "All":
            score += 1.5

        # Category cue bonuses
        for cue, pat in (
            (r"\b(dental|dentist|oral|teeth)\b", r"\b(dental|dentist|oral)\b"),
            (r"\b(pediatric|children|kids)\b", r"\b(pediatric|children|youth)\b"),
            (r"\b(mental|therapy|counseling)\b", r"\b(mental|therapy|counseling)\b"),
            (r"\b(legal|immigration|asylum)\b", r"\b(legal|immigration|asylum)\b"),
            (r"\b(esl|english|ged)\b", r"\b(esl|english|ged|literacy)\b"),
            (r"\b(shelter|housing)\b", r"\b(shelter|housing)\b"),
        ):
            if re.search(cue, q_raw or " ".join(terms), re.I) and re.search(pat, haystack, re.I):
                score += 2.0

        if wants_timing:
            is_open = search.is_open_now(c)
            c["_is_open_now"] = is_open
            if is_open:
                score += 1.5
        else:
            c["_is_open_now"] = False

        # Keep near-misses with real signal; drop pure noise
        if not terms:
            if score >= 0.4:
                ranked.append((max(score, 0.5), c))
            continue
        if term_hits == 0 and not (require and must_ok) and not (target_zip and zip_tier in ("exact", "nearby")):
            if fuzzy < 0.48:
                continue
        if score >= 0.55:
            ranked.append((score, c))

    # Prefer exact ZIP, then nearby, then score
    def _sort_key(pair):
        sc, item = pair
        tier = item.get("_zip_tier")
        tier_rank = 0 if tier == "exact" else (1 if tier == "nearby" else 2)
        open_rank = -int(item.get("_is_open_now", False)) if wants_timing else 0
        return (tier_rank, open_rank, -sc, item.get("name") or "")

    ranked.sort(key=_sort_key)
    return ranked

def is_pinned(cat_key: str, item_id: str) -> bool:
    return any(p["cat"] == cat_key and p["id"] == item_id for p in st.session_state["pinned"])


def _prompt_preview(text: str, n: int = 48) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def render_prompt_rail(prompts: List[Tuple[int, str]]) -> None:
    """
    ChatGPT-style vertical tick rail on the RIGHT.
    One mark per user prompt; click jumps back to that turn.
    Active mark uses brand green (#4EB086).
    """
    if len(prompts) < 2:
        return

    import json
    import streamlit.components.v1 as components

    items = [
        {"id": f"aidr-prompt-{idx}", "title": _prompt_preview(txt), "n": i + 1}
        for i, (idx, txt) in enumerate(prompts)
    ]
    payload = json.dumps(items)

    components.html(
        f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head><body>
<script>
(function () {{
  const items = {payload};
  const doc = window.parent.document;

  doc.querySelectorAll(".aidr-prompt-rail").forEach((el) => el.remove());

  let style = doc.getElementById("aidr-prompt-rail-css");
  if (!style) {{
    style = doc.createElement("style");
    style.id = "aidr-prompt-rail-css";
    doc.head.appendChild(style);
  }}
  style.textContent = `
      .aidr-prompt-rail {{
        position: fixed;
        right: 14px;
        top: 50%;
        transform: translateY(-50%);
        z-index: 1000;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        padding: 12px 8px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.82);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 4px 18px rgba(26, 46, 40, 0.08);
        border: 1px solid rgba(78, 176, 134, 0.28);
      }}
      .aidr-prompt-rail button.aidr-tick {{
        width: 20px;
        height: 3.5px;
        border: none;
        border-radius: 999px;
        padding: 0;
        margin: 0;
        cursor: pointer;
        background: rgba(90, 115, 104, 0.35);
        transition: background 0.15s ease, width 0.15s ease, box-shadow 0.15s ease;
      }}
      .aidr-prompt-rail button.aidr-tick:hover {{
        background: rgba(78, 176, 134, 0.55);
        width: 24px;
      }}
      .aidr-prompt-rail button.aidr-tick.active {{
        background: #4EB086;
        width: 26px;
        box-shadow: 0 0 0 3px rgba(78, 176, 134, 0.22);
      }}
      @media (max-width: 768px) {{
        .aidr-prompt-rail {{ right: 6px; padding: 10px 6px; gap: 8px; }}
        .aidr-prompt-rail button.aidr-tick {{ width: 14px; }}
        .aidr-prompt-rail button.aidr-tick.active {{ width: 20px; }}
      }}
    `;

  const rail = doc.createElement("nav");
  rail.className = "aidr-prompt-rail";
  rail.setAttribute("aria-label", "Jump to earlier prompts");

  function setActive(id) {{
    rail.querySelectorAll("button.aidr-tick").forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.target === id);
    }});
  }}

  items.forEach((item, i) => {{
    const btn = doc.createElement("button");
    btn.type = "button";
    btn.className = "aidr-tick" + (i === items.length - 1 ? " active" : "");
    btn.dataset.target = item.id;
    btn.title = "Prompt " + item.n + ": " + item.title;
    btn.setAttribute("aria-label", btn.title);
    btn.addEventListener("click", () => {{
      const target = doc.getElementById(item.id);
      if (target) {{
        target.scrollIntoView({{ behavior: "smooth", block: "start" }});
        setActive(item.id);
      }}
    }});
    rail.appendChild(btn);
  }});

  doc.body.appendChild(rail);

  // Highlight the tick for whichever prompt is nearest the viewport
  const anchors = items
    .map((it) => doc.getElementById(it.id))
    .filter(Boolean);
  if (anchors.length && "IntersectionObserver" in window.parent) {{
    const io = new window.parent.IntersectionObserver(
      (entries) => {{
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0] && visible[0].target && visible[0].target.id) {{
          setActive(visible[0].target.id);
        }}
      }},
      {{ root: null, rootMargin: "-20% 0px -55% 0px", threshold: [0, 0.25, 0.6] }}
    );
    anchors.forEach((a) => io.observe(a));
  }}
}})();
</script>
</body></html>
        """,
        height=0,
        width=0,
    )


def toggle_pin(cat_key: str, item: Dict):
    """Toggle pin state for an item. Returns True if pinned, False if unpinned."""
    current_pinned = st.session_state.get("pinned", [])
    
    # Check if already pinned
    existing_index = None
    for i, p in enumerate(current_pinned):
        if p["cat"] == cat_key and p["id"] == item["id"]:
            existing_index = i
            break
    
    if existing_index is not None:
        # Unpin: remove from list
        current_pinned.pop(existing_index)
        st.session_state["pinned"] = current_pinned
        return False
    else:
        # Pin: add to list
        pin_data = {
            "cat": cat_key, 
            "id": item["id"], 
            "name": item["name"], 
            "website": item.get("website")
        }
        st.session_state["pinned"] = current_pinned + [pin_data]
        return True

def friendly_intro(category: str, query: str, zip_filter: str, lang_filter: str, service_filter: str = "All", day_filter: str = "All", detected_zip: str = None, detected_service: str = None, detected_day: str = None) -> str:
    """Pip intro in the active UI language."""
    _cl = st.session_state.get("ui_lang_code", "en")
    q = (query or "").strip() or "…"
    z = detected_zip or (zip_filter if zip_filter != "All" else None)
    svc = detected_service or (service_filter if service_filter != "All" else None)
    return i18n.results_intro(category, q, _cl, zip_code=z, service=svc)


def _specialty_tags(item: Dict, cat_key: str) -> List[str]:
    """Full specialty / category chips for Yelp-style cards (deduped)."""
    tags: List[str] = []
    seen = set()

    def norm(t: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (t or "").lower())

    def add(t: str) -> None:
        t = (t or "").strip()
        if not t:
            return
        key = norm(t)
        if not key or key in seen:
            return
        seen.add(key)
        tags.append(t)

    if "health" in cat_key.lower():
        add("Healthcare")
    elif "education" in cat_key.lower():
        add("Education")
    else:
        add("Legal & Shelter")

    # Ryan White / HAB context first so cards show program clearly
    blob = " ".join(
        [
            str(item.get("services_text") or ""),
            str(item.get("search_blob") or ""),
            " ".join(item.get("subcategories") or []),
            str(item.get("notes") or ""),
        ]
    ).lower()
    if re.search(r"ryan\s*white|hrsa\s*hab", blob):
        add("Ryan White HIV/AIDS Program")

    for s in item.get("subcategories") or []:
        add(str(s))

    # Prefer human labels from services_text over snake_case service keys
    stxt = item.get("services_text") or ""
    stxt = re.sub(r"^.*?Services:\s*", "", str(stxt), flags=re.I)
    stxt = stxt.replace("🏥", "").strip()
    parsed = [p.strip(" .") for p in re.split(r"[;|•·]", stxt) if p.strip(" .")]
    for part in parsed:
        add(part)

    if not parsed:
        services = item.get("services") or []
        if isinstance(services, list):
            for s in services:
                add(str(s).replace("_", " ").title())
        elif services:
            add(str(services))

    for badge in item.get("availability_badges") or []:
        add(str(badge))

    return tags


def render_card(idx: int, item: Dict, cat_key: str, user_need: str = "", key_suffix: str = ""):
    """Yelp-style listing — ≤4 specialty chips (+▾); Details / Pin / Map / Comments."""
    import map_utils
    from data_loader import normalize_address

    is_open = bool(item.get("_is_open_now")) if "_is_open_now" in item else False
    _cl = st.session_state.get("ui_lang_code", "en")
    addr = normalize_address(item.get("address") or "")
    uid = f"{cat_key}_{item['id']}_{idx}{key_suffix}"
    name = item.get("name") or "Unknown"
    tags = [i18n.localize_term(t, _cl) for t in _specialty_tags(item, cat_key)]

    langs = item.get("languages")
    if isinstance(langs, list):
        lang_str = i18n.localize_language_list(langs, _cl)
    else:
        lang_str = i18n.localize_language_list(str(langs or ""), _cl)

    hours_display = item.get("hours_text") or item.get("hours")
    hours_str = ""
    if hours_display and not isinstance(hours_display, dict):
        hours_str = re.sub(r"^(?:⏰\s*)?Hours?:\s*", "", str(hours_display), flags=re.I).strip()
        hours_str = i18n.localize_hours(hours_str, _cl)

    def html_escape(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    open_chip = (
        f'<span class="yelp-chip yelp-open">{html_escape(i18n.t("open_now_chip", _cl))}</span>'
        if is_open
        else ""
    )

    visible = tags[:4]
    extra = tags[4:]
    chips = "".join(f'<span class="yelp-chip">{html_escape(t)}</span>' for t in visible)
    if extra:
        extra_html = "".join(
            f'<span class="yelp-chip">{html_escape(t)}</span>' for t in extra
        )
        # summary stays in the same flex row as the first 4; extras wrap below when open
        chips += (
            f'<details class="yelp-chip-more">'
            f'<summary class="yelp-chip yelp-chip-drop" title="More specialties">▾</summary>'
            f'<span class="yelp-chip-extra">{extra_html}</span>'
            f"</details>"
        )

    # Phone / website — always show (Yelp-style contact lines)
    phone = (item.get("phone") or "").strip()
    phone = re.sub(r"^📞\s*", "", phone).strip()
    phone_digits = (item.get("phone_digits") or "").strip()
    if not phone and phone_digits:
        phone = phone_digits
    if not phone:
        blob = item.get("search_blob") or item.get("services_text") or ""
        m = re.search(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", str(blob))
        if m:
            phone = m.group(0)
    website = (item.get("website") or "").strip()
    website = re.sub(r"^🌐\s*", "", website).strip()
    if not website:
        blob = item.get("search_blob") or item.get("services_text") or ""
        m = re.search(r"https?://[^\s<>\"]+", str(blob))
        if m:
            website = m.group(0).rstrip(".,);")

    facts = []
    if addr:
        facts.append(f'<div class="yelp-fact">📍 {html_escape(addr)}</div>')
    if phone:
        tel = re.sub(r"\D", "", phone)
        if len(tel) >= 10:
            facts.append(
                f'<div class="yelp-fact">📞 <a href="tel:{html_escape(tel)}">{html_escape(phone)}</a></div>'
            )
        else:
            facts.append(f'<div class="yelp-fact">📞 {html_escape(phone)}</div>')
    else:
        facts.append('<div class="yelp-fact yelp-fact-muted">📞 Phone not listed</div>')
    if website:
        facts.append(
            f'<div class="yelp-fact">🔗 <a href="{html_escape(website)}" target="_blank" '
            f'rel="noopener noreferrer">{html_escape(website)}</a></div>'
        )
    else:
        facts.append('<div class="yelp-fact yelp-fact-muted">🔗 Website not listed</div>')
    if lang_str:
        facts.append(f'<div class="yelp-fact">🗣 {html_escape(lang_str)}</div>')
    if hours_str:
        facts.append(f'<div class="yelp-fact">⏰ {html_escape(hours_str)}</div>')
    facts_html = "".join(facts)

    # on_click + early switch_page (see session init) = one click navigation.
    # Mid-script switch_page / changing pin keys caused a “need 2 presses” feel.
    _rid = str(item["id"])

    def _go_detail():
        st.session_state["current_resource_id"] = _rid
        st.session_state["current_category"] = cat_key
        st.session_state["scroll_to_comments"] = False
        st.session_state["_nav_detail"] = True

    def _go_comments():
        st.session_state["current_resource_id"] = _rid
        st.session_state["current_category"] = cat_key
        st.session_state["scroll_to_comments"] = True
        st.session_state["_nav_detail"] = True

    def _do_pin():
        toggle_pin(cat_key, item)

    with st.container():
        st.markdown(
            f"""
<div class="yelp-card">
  <div class="yelp-card-head">
    <span class="yelp-idx">{idx}</span>
    <div class="yelp-card-main">
      <p class="yelp-name">{html_escape(name)} {open_chip}</p>
      <div class="yelp-chips">{chips}</div>
      <div class="yelp-facts">{facts_html}</div>
    </div>
  </div>
</div>
<style>
.yelp-card {{
  background: #fff;
  border: 1px solid rgba(26,46,40,0.12);
  border-radius: 12px;
  padding: 0.9rem 1rem 0.35rem 1rem;
  margin: 0.65rem 0 0.25rem 0;
  box-shadow: 0 1px 3px rgba(26,46,40,0.06);
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.yelp-card-head {{ display: flex; gap: 0.75rem; align-items: flex-start; }}
.yelp-idx {{
  flex-shrink: 0; width: 1.6rem; height: 1.6rem;
  border-radius: 6px; background: #4EB086; color: #fff;
  font-weight: 700; font-size: 0.85rem;
  display: flex; align-items: center; justify-content: center;
  margin-top: 0.1rem;
}}
.yelp-name {{
  margin: 0 0 0.4rem 0; font-size: 1.08rem; font-weight: 700; color: #1a2e28; line-height: 1.3;
}}
.yelp-chips {{ display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.45rem; align-items: center; }}
.yelp-chip {{
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.72rem; font-weight: 600;
  padding: 0.15rem 0.5rem; border-radius: 4px;
  background: #eef7f2; color: #2d6b54; border: 1px solid rgba(78,176,134,0.25);
  line-height: 1.2; box-sizing: border-box;
}}
.yelp-chip.yelp-open {{ background: #10b981; color: #fff; border-color: #10b981; }}
/* Keep ▾ in the same flex row as the first 4 chips */
.yelp-chip-more {{ display: contents; }}
.yelp-chip-more > summary {{
  list-style: none; cursor: pointer; user-select: none;
  min-width: 1.55rem; padding-left: 0.35rem; padding-right: 0.35rem;
}}
.yelp-chip-more > summary::-webkit-details-marker {{ display: none; }}
.yelp-chip-drop:hover {{ background: #dff3ea; }}
.yelp-chip-extra {{ display: contents; }}
.yelp-chip-more:not([open]) > .yelp-chip-extra {{ display: none; }}
.yelp-chip-more[open] > summary {{ order: 999; }}
.yelp-facts {{ margin: 0.15rem 0 0.35rem 0; }}
.yelp-fact {{
  font-size: 0.86rem; color: #4a5f56; line-height: 1.45; margin: 0.12rem 0;
}}
.yelp-fact-muted {{ color: #8a9e95; font-style: italic; }}
.yelp-fact a {{ color: #3d9a72; font-weight: 600; text-decoration: none; }}
.yelp-fact a:hover {{ text-decoration: underline; }}
</style>
""",
            unsafe_allow_html=True,
        )

        # Details | Pin | Map | Comments — equal pills, no robot / no chevron panel
        c_details, c_pin, c_map, c_comments = st.columns(4, gap="medium")

        with c_details:
            st.button(
                i18n.t("details_short", _cl),
                key=f"detail_{uid}",
                use_container_width=True,
                on_click=_go_detail,
            )

        with c_pin:
            pinned_now = is_pinned(cat_key, item["id"])
            st.button(
                i18n.t("unpin" if pinned_now else "pin", _cl),
                key=f"pin_{uid}",
                use_container_width=True,
                on_click=_do_pin,
            )

        with c_map:
            if addr:
                map_utils.maps_action_button(
                    i18n.t("map_short", _cl),
                    addr,
                    key=f"map_{uid}",
                    place_name=name,
                )
            else:
                st.button(
                    i18n.t("map_short", _cl),
                    key=f"map_disabled_{uid}",
                    disabled=True,
                    use_container_width=True,
                )

        with c_comments:
            st.button(
                i18n.t("comments_short", _cl),
                key=f"comments_{uid}",
                use_container_width=True,
                on_click=_go_comments,
            )



def render_results_block(results: List[Dict], category: str, intro: str = "", block_id: str = "main"):
    """List results with Pip intro. Per-card Map opens Apple/Google chooser."""
    if intro:
        mascot.pip_say(intro)

    for i, c in enumerate(results, 1):
        render_card(i, c, category, key_suffix=f"_{block_id}")
    st.caption(i18n.t("more_caption", st.session_state.get("ui_lang_code", "en")))

# ===========================
# Session State
# ===========================
st.session_state.setdefault("category", "Healthcare")
st.session_state.setdefault("datasets_cache", {})
st.session_state.setdefault("messages", [])  # [{"role":"user","text":...}, {"role":"assistant","text"/"render":...}]
st.session_state.setdefault("pinned", [])
st.session_state.setdefault("last_query_by_cat", {})
st.session_state.setdefault("shown_ids_by_cat", {})
st.session_state.setdefault("misspelling_suggestion", None)
st.session_state.setdefault("pending_spell_check", None)  # {original, corrected, fixes}
st.session_state.setdefault("aidr_smart_llm", False)

# Initialize conversation ID for database logging
if "convo_id" not in st.session_state:
    st.session_state["convo_id"] = uuid.uuid4().hex[:12]

# Clear sticky Map-dialog flags (old pattern reopened dialog on every widget click)
if not st.session_state.get("_maps_flags_cleared"):
    for _k in list(st.session_state.keys()):
        if isinstance(_k, str) and _k.startswith("_maps_open_"):
            del st.session_state[_k]
    st.session_state.pop("_maps_ctx", None)
    st.session_state["_maps_flags_cleared"] = True

# One-click Details / Comments: callbacks set this before the script body runs
if st.session_state.pop("_nav_detail", False):
    st.switch_page("pages/_clinic_detail.py")


# ===========================
# Sidebar — Language → Account → Forms → Saved → Filters
# ===========================
ui_lang = _ui_lang0

with st.sidebar:
    # Account + status (language already rendered above hero)
    with st.expander(i18n.t("auth", ui_lang), expanded=False):
        auth.render_auth_sidebar(ui_lang)
        status = llm_service.llm_status()
        if status["available"]:
            st.success(f"{i18n.t('ai_online', ui_lang)} · {status['provider']}")
        else:
            st.warning(i18n.t("ai_offline", ui_lang))
            st.caption(i18n.t("ollama_hint", ui_lang))
        st.caption(i18n.t("whatsapp_hint", ui_lang))

    # Voice — Pip speaks replies (free browser TTS)
    import core.voice as voice

    st.markdown('<hr class="aidr-side-rule"/>', unsafe_allow_html=True)
    voice.render_voice_toggle(ui_lang)
    st.toggle(
        "Smarter answers (slower)",
        key="aidr_smart_llm",
        help="Uses local Ollama for understanding — slower. Off = fast search.",
    )
    st.markdown('<hr class="aidr-side-rule"/>', unsafe_allow_html=True)

    # Forms
    import core.forms as forms

    with st.expander(i18n.t("forms_section", ui_lang), expanded=True):
        st.markdown(f'<p class="aidr-side-title">{i18n.t("forms_users", ui_lang)}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="aidr-side-cap">{i18n.t("forms_users_cap", ui_lang)}</p>', unsafe_allow_html=True)
        st.link_button(
            i18n.t("forms_users_btn", ui_lang),
            forms.community_report_url(),
            use_container_width=True,
        )
        st.markdown("")
        st.markdown(f'<p class="aidr-side-title">{i18n.t("forms_clinics", ui_lang)}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="aidr-side-cap">{i18n.t("forms_clinics_cap", ui_lang)}</p>', unsafe_allow_html=True)
        st.link_button(
            i18n.t("forms_clinics_btn", ui_lang),
            forms.clinic_update_url(),
            use_container_width=True,
        )

    # 4) Saved — always open the place website (external), never a chat page
    with st.expander(i18n.t("pinned", ui_lang), expanded=False):
        if st.session_state["pinned"]:
            for i, p in enumerate(st.session_state["pinned"], 1):
                name = p.get("name") or "Saved place"
                website = (p.get("website") or "").strip()
                if website:
                    st.link_button(f"{i}. {name}", website, use_container_width=True)
                else:
                    st.caption(f"{i}. {name} — no website listed")
        else:
            st.caption(i18n.t("pinned_empty", ui_lang))

    # 5) Recent (optional)
    with st.expander(i18n.t("recent", ui_lang), expanded=False):
        try:
            search_helpers.render_recent_searches(st.session_state["category"])
        except Exception:
            st.caption("—")

    st.markdown('<hr class="aidr-side-rule"/>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="aidr-side-title">{i18n.t("filters", ui_lang)}</p>',
        unsafe_allow_html=True,
    )

# ===========================
# Category — sticky “What do you need?” bar
# ===========================
_ui_lang = st.session_state.get("ui_lang_code", "en")
with st.container(key="aidr_cat_bar"):
    st.markdown(
        f"<p class='aidr-cat-label'>{i18n.t('category_label', _ui_lang)}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<style>
.aidr-cat-label {
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: 1.05rem; font-weight: 700; color: #1a2e28;
  margin: 0 0 0.45rem 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    _cat_order = ["Healthcare", "Education", "Resettlement / Legal / Shelter"]
    _cat_keys = ["healthcare", "education", "resettlement"]
    chip_cols = st.columns(3)
    for i, (cat, key) in enumerate(zip(_cat_order, _cat_keys)):
        with chip_cols[i]:
            selected = st.session_state.get("category") == cat
            if st.button(
                i18n.t(key, _ui_lang),
                key=f"cat_chip_{key}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                st.session_state["category"] = cat
                st.rerun()
cat_choice = st.session_state["category"]

# ===========================
# Load dataset - NOW USING data_loader.py for structured JSON!
# ===========================
def get_dataset(cat_key: str) -> Tuple[List[Dict], str]:
    """Load dataset using data_loader.py for structured JSON data."""
    # Use data_loader for fast, structured JSON loading
    try:
        items = data_loader.load_category_data(cat_key)
        
        # For backward compatibility, we still need raw_text for filter building
        # But we can build it from the structured data if needed
        if cat_key not in st.session_state.get("raw_text_cache", {}):
            # Build raw text representation from structured data for filter options
            raw_text_parts = []
            for item in items[:100]:  # Sample for performance
                raw_text_parts.append(f"{item.get('name', '')} {item.get('address', '')} {item.get('services_text', '')}")
            raw_text = "\n".join(raw_text_parts)
            st.session_state.setdefault("raw_text_cache", {})[cat_key] = raw_text
        else:
            raw_text = st.session_state["raw_text_cache"][cat_key]
        
        return items, raw_text
    except Exception as e:
        # Fallback to old parsing if data_loader fails
        st.warning(f"⚠️ Using fallback parsing (data_loader failed: {e})")
        if cat_key in st.session_state.get("datasets_cache", {}):
            return st.session_state["datasets_cache"][cat_key]
        text = fetch_text_from_sources(DATA_SOURCES[cat_key])
        items = parse_blocks(text)
        st.session_state.setdefault("datasets_cache", {})[cat_key] = (items, text)
        return items, text

try:
    items, raw_text = get_dataset(st.session_state["category"])
except Exception as e:
    st.error(f"⚠️ Could not load the **{st.session_state['category']}** dataset. Check the GitHub/raw path or local fallback.\n\n{e}")
    st.stop()

# Build filter options from the loaded dataset
all_zips = sorted(set(re.findall(r"\b60\d{3}\b", raw_text)))
lang_lines = re.findall(r"🗣\s*Languages:\s*(.+)", raw_text)
langs = set()
for line in lang_lines:
    for lang in re.split(r"[;,]", line):
        lang = lang.strip()
        if lang and not lang.lower().startswith("and"):
            langs.add(lang)
all_langs = sorted(langs)

# Build service filter options based on category
# Use structured data if available
service_options = ["All"]
if items and isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict) and "services" in items[0]:
    # Extract unique services from structured data
    all_services = set()
    for item in items:
        services = item.get("services", [])
        if isinstance(services, list):
            all_services.update(services)
        elif services:
            # Old format: string
            all_services.add(services)
    service_options.extend(sorted([s.replace("_", " ").title() for s in all_services if s]))
else:
    # Fallback to hardcoded options
    if cat_choice == "Healthcare":
        service_options.extend(["dental", "pediatric", "mental health", "women's health", "immunization", "primary care"])
    elif cat_choice == "Education":
        service_options.extend(["ESL", "GED/Citizenship", "Youth Programs", "Tutoring", "Literacy"])
    elif cat_choice == "Resettlement / Legal / Shelter":
        service_options.extend(["Legal Services", "Shelter/Housing", "Benefits Assistance", "Resettlement Services"])

# Build day of week filter options from actual hours data
day_options = ["All"]
available_days = set()

# Extract available days from hours data using smart parsing
for item in items:
    # Try hours_text first (from .txt), then structured hours
    hours = item.get("hours_text") or item.get("hours") or ""
    if hours:
        # Use the smart parsing function (handles both dict and string)
        days_found = parse_day_ranges(hours)
        for day in days_found:
            available_days.add(day)

# Add available days to options, sorted
day_options.extend(sorted(available_days))

# Tip about auto-detection features (now that day_options is defined)
if len(day_options) > 1:
    tip_text = i18n.t("tip_search_days", _ui_lang)
else:
    tip_text = i18n.t("tip_search", _ui_lang)

with st.sidebar:
    _all = i18n.t("filter_all", _ui_lang)
    # Keep internal "All" key for filter logic; show translated label via format if needed
    zip_opts = ["All"] + all_zips
    lang_opts = ["All"] + all_langs
    zip_filter = st.selectbox(
        i18n.t("filter_zip", _ui_lang),
        zip_opts,
        format_func=lambda x: _all if x == "All" else x,
        key=f"zip_{cat_choice}",
    )
    lang_filter = st.selectbox(
        i18n.t("filter_lang", _ui_lang),
        lang_opts,
        format_func=lambda x: _all if x == "All" else x,
        key=f"lang_{cat_choice}",
    )
    service_filter = st.selectbox(
        i18n.t("filter_service", _ui_lang),
        service_options,
        format_func=lambda x: _all if x == "All" else x,
        key=f"service_{cat_choice}",
    )
    
    if len(day_options) > 1:
        day_filter = st.selectbox(
            i18n.t("filter_day", _ui_lang),
            day_options,
            format_func=lambda x: _all if x == "All" else x,
            key=f"day_{cat_choice}",
        )
    else:
        day_filter = "All"
    
    st.caption(tip_text)
    
    neighborhoods = neighborhood_mapping.get_all_neighborhoods()
    if neighborhoods:
        st.caption(i18n.t("tip_neighborhood", _ui_lang))
    
    # QR Code section removed - not necessary
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(i18n.t("reset", _ui_lang), key="reset_chat"):
            st.session_state["messages"] = []
            st.session_state["pinned"] = []
            st.session_state["shown_ids_by_cat"] = {}
            st.session_state["last_query_by_cat"] = {}
            st.session_state["misspelling_suggestion"] = None
            st.session_state["pending_spell_check"] = None
            # Clear datasets cache to force fresh fetch
            st.session_state["datasets_cache"] = {}
            # Clear LLM conversation context
            if "llm_conversation_context" in st.session_state:
                st.session_state["llm_conversation_context"].clear()
            # New API (no deprecation warning)
            try:
                st.query_params.clear()
            except Exception:
                pass
            st.rerun()
    with c2:
        # Use a link to an anchor instead of a button for reliable scrolling
        # Styled to match Streamlit's native button appearance
        st.markdown(
            '''<a href="#bottom" style="
                display:inline-flex;
                align-items:center;
                justify-content:center;
                padding:0.25rem 0.75rem;
                background-color:white;
                border:1px solid rgba(49,51,63,0.2);
                border-radius:0.5rem;
                text-decoration:none;
                color:rgb(49,51,63);
                font-family:Source Sans Pro,sans-serif;
                font-size:1rem;
                font-weight:400;
                line-height:1.6;
                cursor:pointer;
                min-height:38.4px;
                width:100%;
                box-sizing:border-box;
            " onmouseover="this.style.borderColor=\'rgb(255,75,75)\';this.style.color=\'rgb(255,75,75)\'" onmouseout="this.style.borderColor=\'rgba(49,51,63,0.2)\';this.style.color=\'rgb(49,51,63)\'">⏬ Scroll to Latest</a>''',
            unsafe_allow_html=True
        )



# ===========================
# Response function definition
# ===========================
def respond_to_query(user_text: str, category: str):
    is_more = user_text.strip().lower() == "more"
    
    # Get conversation context for follow-up handling
    context = llm_service.get_conversation_context()
    context.add_user_message(user_text)

    # 1) Load dataset first (required before using items)
    items, _ = get_dataset(category)  # get_dataset returns (items, category_str)
    if not items:
        with st.chat_message("assistant", avatar=mascot.PIP_AVATAR):
            st.error(f"❌ Could not load {category} data. Please try again.")
        return

    # 2) Use LLM to understand the query (if available)
    llm_result = None
    detected_zip = None
    detected_service = None
    detected_day = None
    user_language = "English"
    understood_need = user_text
    
    # Fast path: regex detectors (skip slow Ollama intent unless toggled on)
    use_smart = st.session_state.get("aidr_smart_llm", False)

    if not is_more:
        if use_smart:
            llm_result = llm_service.process_query_with_llm(user_text, category)
            if llm_result.get("is_follow_up") and llm_result.get("follow_up_type"):
                follow_up_type = llm_result["follow_up_type"]
                if follow_up_type != "more_results":
                    filtered_results, explanation = llm_service.handle_follow_up(
                        user_text,
                        follow_up_type,
                        context.last_results,
                        context.last_all_results,
                    )
                    if filtered_results:
                        # No st.chat_message — avoids Streamlit’s orange robot avatar
                        mascot.pip_say(explanation or "Here you go!")
                        for i, c in enumerate(filtered_results, 1):
                            render_card(i, c, category, user_text)
                        context.set_results(filtered_results, context.last_all_results, category)
                        st.session_state["messages"].append({
                            "role": "assistant",
                            "render": "cards",
                            "category": category,
                            "results": filtered_results,
                            "text": explanation,
                        })
                        return
                    mascot.pip_say(explanation or "I couldn't find that filter. Try another ask?")
                    return

            user_language = llm_result.get("user_language", "English")
            understood_need = llm_result.get("understood_need", user_text)
            llm_filters = llm_result.get("filters", {})
            detected_zip = llm_filters.get("zip")
            detected_service = llm_result.get("service_type")
            detected_day = llm_filters.get("day")

        preferred = st.session_state.get("preferred_language", "Auto-detect")
        if preferred and preferred != "Auto-detect":
            user_language = preferred

        if not detected_zip:
            known_zips = [
                str(c.get("zip_code") or c.get("zip") or "").strip()
                for c in items
                if str(c.get("zip_code") or c.get("zip") or "").strip()
            ]
            detected_zip = detect_zip_from_query(user_text, known_zips)
        if not detected_service:
            detected_service = detect_service_from_query(user_text, category)
        if not detected_day:
            detected_day = detect_day_from_query(user_text)
    
    # 3) Decide query
    if is_more:
        query = st.session_state["last_query_by_cat"].get(category, "")
    else:
        # Use cleaned query from LLM if available, otherwise use original
        query = llm_result.get("cleaned_query", user_text) if llm_result else user_text
        if category == "Healthcare":
            query = re.sub(r"\bclinic(s)?\b", "", query, flags=re.IGNORECASE)
        st.session_state["last_query_by_cat"][category] = query

    # Only use detected day if it's actually available in the dataset
    if detected_day and not is_day_available_in_dataset(detected_day, items):
        detected_day = None
    
    if detected_zip or detected_service or detected_day:
        # Clean the query to avoid double-counting
        query = clean_query_of_service_and_day(query, detected_service, detected_day)
        if detected_zip:
            query = clean_query_of_zip(query)
        st.session_state["last_query_by_cat"][category] = query
    
    # 4) Rank with current filters (auto-detected values take priority over sidebar)
    zf = detected_zip or st.session_state.get(f"zip_{category}", "All") or "All"
    lf = st.session_state.get(f"lang_{category}", "All") or "All"
    sf = detected_service or st.session_state.get(f"service_{category}", "All") or "All"
    df = detected_day or st.session_state.get(f"day_{category}", "All") or "All"
    
    # Apply quick filters if any are active
    try:
        quick_filters = st.session_state.get(f"quick_filters_{category}", {})
        if any(quick_filters.values()):
            items = search_helpers.filter_by_quick_filters(items, quick_filters)
    except:
        pass
    
    ranked = rank_items(items, query, category, zf, lf, sf, df, soft_filters=True)

    # Soft retry: keep ZIP cluster; only drop day/service first, then ZIP last
    if not ranked and (df != "All" or sf != "All"):
        ranked = rank_items(
            items, query, category, zf, lf, "All", "All", soft_filters=True
        )
    if not ranked and zf != "All":
        ranked = rank_items(
            items, query, category, "All", lf, "All", "All", soft_filters=True
        )

    # "more" skips clinics already shown; a new query resets that list
    shown_map = st.session_state["shown_ids_by_cat"]
    if is_more:
        prev_ids = set(shown_map.get(category, []))
        fresh = [c for _, c in ranked if c["id"] not in prev_ids]
    else:
        prev_ids = set()
        shown_map[category] = []
        fresh = [c for _, c in ranked]
    to_show = fresh[:TOP_N]

    # Store results in context for follow-up handling
    context.set_results(to_show, [c for _, c in ranked], category)

    # 5) Assistant reply — Pip via pip_say only (no chat_message = no orange robot)
    if not is_more:
        with st.spinner("Pip is looking…"):
            pass

    if to_show:
        # Fast default: template Pip intro (no Ollama wait). Smart LLM optional.
        if use_smart and llm_service.is_llm_available() and not is_more:
            intro = llm_service.generate_response(
                user_text, to_show, category,
                context.get_context_messages()
            )
            # Prefer sidebar UI language for Pip's spoken/written intro
            _ui = st.session_state.get("ui_lang_code", "en")
            target = i18n.CODE_TO_NAME.get(_ui) or user_language or "English"
            if target and str(target).lower() not in ("english", "en"):
                intro = llm_service.translate_response_if_needed(
                    intro, target, include_english=False
                )
            context.add_assistant_message(intro)
        else:
            intro = friendly_intro(category, query, zf, lf, sf, df, detected_zip, detected_service, detected_day)

        timing_keywords = ["now", "today", "open", "available", "immediate", "urgent"]
        timing_note = ""
        if any(kw in query.lower() for kw in timing_keywords):
            open_count = sum(1 for item in to_show if item.get("_is_open_now", False))
            if open_count > 0:
                timing_note = f"\n\n🟢 {open_count} open now"

        # Clarify nearby-ZIP results when nothing exact matched in this batch
        tiers = [c.get("_zip_tier") for c in to_show]
        if zf and zf != "All" and "nearby" in tiers and "exact" not in tiers:
            timing_note += (
                f"\n\n📍 No exact listings in **{zf}** — showing nearby ZIP areas instead."
            )
        elif zf and zf != "All" and "nearby" in tiers:
            timing_note += "\n\n📍 Including nearby ZIP areas as well."

        shown_map[category] = list(prev_ids | {c["id"] for c in to_show})
        render_results_block(to_show, category, intro=intro + timing_note, block_id="live")

        try:
            import core.voice as voice
            st.session_state["last_answer"] = intro
            voice.speak_pip(intro, lang=st.session_state.get("ui_lang_code", "en"))
        except Exception:
            pass

        # Add to recent searches
        if not is_more:
            try:
                search_helpers.add_to_recent_searches(query, category)
            except Exception:
                pass

        # Persist assistant block
        st.session_state["messages"].append({
            "role": "assistant",
            "render": "cards",
            "category": category,
            "results": to_show,
            "text": intro
        })

        # Log assistant message to database
        def summarize_results(results):
            lines = []
            for r in results:
                name = r.get("name") or "Unknown"
                addr = r.get("address") or ""
                phone = r.get("phone") or ""
                lines.append(f"{name} | {addr} | {phone}")
            return "\n".join(lines[:10])

        reply_text = summarize_results(to_show)
        reply_json = {"category": category, "results": to_show}
        db.save_assistant_message(
            convo_id=st.session_state["convo_id"],
            reply_text=reply_text,
            reply_json=reply_json,
            category=category
        )
    else:
        if is_more:
            mascot.pip_say(
                "That’s everything I found for this search. Try a different ZIP, service, or neighborhood — or tap a suggestion below."
            )
        else:
            mascot.pip_say(
                f"I couldn’t find a close match for **{user_text}** in {category}. "
                "Try a broader ask, or tap a suggestion:"
            )

        # Clear suggestion buttons from the dataset + related searches
        try:
            suggestions = search_helpers.get_no_result_suggestions(user_text, category, items)
        except Exception:
            suggestions = []
        if not suggestions:
            suggestions = {
                "Healthcare": ["dental", "primary care", "mental health", "women's health", "free clinic"],
                "Education": ["ESL", "GED", "citizenship", "job training"],
                "Resettlement / Legal / Shelter": ["legal help", "immigration", "shelter", "food pantry"],
            }.get(category, ["primary care", "ESL", "legal help"])

        sugg_cols = st.columns(min(len(suggestions), 5))
        for i, suggestion in enumerate(suggestions[:5]):
            with sugg_cols[i]:
                if st.button(
                    suggestion,
                    key=f"nores_sugg_{category}_{i}_{abs(hash(suggestion)) % 10_000}",
                    use_container_width=True,
                ):
                    st.session_state[f"search_suggestion_{category}"] = suggestion
                    st.rerun()

        st.caption("National backups: [FindHelp.org](https://www.findhelp.org) · [211.org](https://www.211.org)")

        st.session_state["messages"].append({
            "role": "assistant",
            "text": f"No matches for '{user_text}'. Suggested: {', '.join(suggestions[:5])}",
        })

        reply_text = "No matches in dataset (suggestions offered)."
        reply_json = {"category": category, "results": [], "suggestions": suggestions[:5]}
        db.save_assistant_message(
            convo_id=st.session_state["convo_id"],
            reply_text=reply_text,
            reply_json=reply_json,
            category=category
        )
 
# ===========================
# Chat input + spell check (single input — chat bar only)
# ===========================
_chip_lang = st.session_state.get("ui_lang_code", "en")
placeholder_text = i18n.t("ask_placeholder", _chip_lang)

# Seed vocab once per session (synonyms + any cached dataset labels)
if not st.session_state.get("_spell_vocab_ready"):
    _seed_items = []
    for _cached in (st.session_state.get("datasets_cache") or {}).values():
        if isinstance(_cached, list):
            _seed_items.extend(_cached)
    _seed_spell_vocab(_seed_items or None)
    st.session_state["_spell_vocab_ready"] = True

prompt = st.chat_input(placeholder_text)

# ===========================
# Re-render previous chat
# ===========================
_user_prompts: List[Tuple[int, str]] = []
for mi, msg in enumerate(st.session_state["messages"]):
    is_cards = msg["role"] == "assistant" and msg.get("render") == "cards"
    if is_cards:
        # No chat_message wrapper — Pip comes from pip_say only (no orange robot)
        render_results_block(
            msg.get("results") or [],
            msg.get("category") or st.session_state.get("category", "Healthcare"),
            intro=msg.get("text") or "",
            block_id=f"hist{mi}",
        )
    else:
        if msg["role"] == "user":
            _user_prompts.append((mi, msg.get("text") or ""))
            st.markdown(
                f'<div id="aidr-prompt-{mi}" class="aidr-prompt-anchor"></div>',
                unsafe_allow_html=True,
            )
        avatar = mascot.PIP_AVATAR if msg["role"] == "assistant" else None
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg.get("text", ""))

# Pending spell confirmation UI (from chat_input path)
_pending_spell = st.session_state.get("pending_spell_check")
if _pending_spell and isinstance(_pending_spell, dict):
    with st.chat_message("assistant", avatar=mascot.PIP_AVATAR):
        fixes = _pending_spell.get("fixes") or []
        bits = ", ".join(f"**{b}** → **{g}**" for b, g in fixes)
        st.info(f"✏️ Before I search — spelling check: {bits}")
        st.markdown(f"Corrected search: **{_pending_spell.get('corrected')}**")
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("Use corrected", key="pending_spell_yes", use_container_width=True):
                q = _pending_spell.get("corrected") or ""
                st.session_state["pending_spell_check"] = None
                st.session_state["messages"].append({"role": "user", "text": q})
                db.save_user_message(
                    convo_id=st.session_state["convo_id"],
                    query_text=q,
                    category=st.session_state["category"],
                    user_label=None,
                )
                respond_to_query(q, st.session_state["category"])
                st.rerun()
        with pc2:
            if st.button("Keep my spelling", key="pending_spell_no", use_container_width=True):
                q = _pending_spell.get("original") or ""
                st.session_state["pending_spell_check"] = None
                st.session_state["messages"].append({"role": "user", "text": q})
                db.save_user_message(
                    convo_id=st.session_state["convo_id"],
                    query_text=q,
                    category=st.session_state["category"],
                    user_label=None,
                )
                respond_to_query(q, st.session_state["category"])
                st.rerun()

# ===========================
# Show current user input immediately (if any)
# ===========================
# Check for search suggestion from sidebar
suggestion_key = f"search_suggestion_{st.session_state['category']}"
if suggestion_key in st.session_state:
    prompt = st.session_state.pop(suggestion_key)
    # Will be processed below

# Mic / dictate → pending prompt (speech-to-text into chat bar)
if not prompt and st.session_state.get("voice_prompt_pending"):
    prompt = st.session_state.pop("voice_prompt_pending")

if prompt and not st.session_state.get("pending_spell_check"):
    spell = spellcheck.check_query(prompt)
    if spell.get("flagged") and not st.session_state.get("_spell_bypass"):
        # Flag before searching — wait for Use corrected / Keep my spelling
        st.session_state["pending_spell_check"] = {
            "original": spell["original"],
            "corrected": spell["corrected"],
            "fixes": spell["fixes"],
        }
        st.rerun()
    else:
        st.session_state.pop("_spell_bypass", None)
        _new_mi = len(st.session_state["messages"])
        st.markdown(
            f'<div id="aidr-prompt-{_new_mi}" class="aidr-prompt-anchor"></div>',
            unsafe_allow_html=True,
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        st.session_state["messages"].append({"role": "user", "text": prompt})

        db.save_user_message(
            convo_id=st.session_state["convo_id"],
            query_text=prompt,
            category=st.session_state["category"],
            user_label=None,
        )
        respond_to_query(prompt, st.session_state["category"])

# Right-side ChatGPT-style prompt rail (2+ user turns)
# Rebuild from session so the newest prompt is included this run.
_rail_prompts: List[Tuple[int, str]] = [
    (i, m.get("text") or "")
    for i, m in enumerate(st.session_state.get("messages") or [])
    if m.get("role") == "user"
]
render_prompt_rail(_rail_prompts)

# Place a bottom anchor for the "Scroll to Latest" link
st.markdown('<div id="bottom" style="height:1px;"></div>', unsafe_allow_html=True)
