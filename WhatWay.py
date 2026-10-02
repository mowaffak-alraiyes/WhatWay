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
from core.retrieval import retrieve as retrieve_resources

# ===========================
# Page & Styles
# ===========================
st.set_page_config(
    page_title="WhatWay",
    page_icon=":material/route:",
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
        f'<p class="ww-side-title">{i18n.t("language_label", _label_lang)}</p>',
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
    st.markdown('<hr class="ww-side-rule"/>', unsafe_allow_html=True)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

/* App text  -  do NOT override Material Icons (fixes keyboard_double_arrow text) */
.stApp, .stMarkdown, .stButton > button, .stSelectbox, .stTextInput,
div[data-testid="stChatMessage"], section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] p,
.ww-hero, .ww-brand, .ww-tag, .ww-brand-lockup, .pip-wrap, .pip-bubble {{
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
  background: #F1F7F3;
}}
/* Wider main column  -  Streamlit default feels too narrow for listings */
.main .block-container {{
  max-width: 1180px !important;
  padding-top: 1.25rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
}}
section[data-testid="stMain"] > div {{
  max-width: none;
}}
.ww-hero {{
  background: #0E6B54;
  border-radius: 22px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 0.9rem;
  color: #fff;
}}
.ww-brand-lockup {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
}}
.ww-route-mark {{
  width: 2.35rem;
  height: 2.35rem;
  flex: 0 0 auto;
}}
.ww-brand {{
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  line-height: 1.1;
  color: #fff !important;
  letter-spacing: -0.03em;
}}
.ww-tag {{
  margin: 0.4rem 0 0 0;
  color: rgba(255,255,255,0.92);
  font-size: 0.98rem;
  max-width: 42rem;
  font-weight: 450;
}}
section[data-testid="stSidebar"] {{
  background: #ffffff;
  border-right: 1px solid #D3E3DA;
}}
section[data-testid="stSidebar"] > div {{
  padding-top: 0.75rem;
}}
/* Even sidebar rhythm */
.ww-side-block {{
  margin: 0 0 1.15rem 0;
  padding: 0;
}}
.ww-side-block h3, .ww-side-title {{
  font-size: 0.78rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #4A5F55 !important;
  margin: 0 0 0.45rem 0 !important;
}}
.ww-side-block .stCaption, .ww-side-cap {{
  margin-top: 0 !important;
  margin-bottom: 0.55rem !important;
  color: #4A5F55 !important;
  font-size: 0.82rem !important;
  line-height: 1.35;
}}
.ww-side-rule {{
  border: none;
  border-top: 1px solid #D3E3DA;
  margin: 0.15rem 0 1.15rem 0;
}}
div[data-testid="stChatMessage"] {{
  background: #fff;
  border-radius: 18px;
  border: 1px solid #DCE9E1;
  padding: 0.45rem 0.6rem;
  box-shadow: none;
}}
.stButton > button {{
  border-radius: 14px !important;
  font-weight: 600 !important;
  min-height: 44px !important;
  transition: transform 160ms cubic-bezier(.32,.72,0,1),
              box-shadow 160ms cubic-bezier(.32,.72,0,1) !important;
}}
.stButton > button:active {{
  transform: scale(0.98);
}}
div.st-key-ww_cat_bar .stButton > button {{
  border-radius: 999px !important;
}}
.stButton > button[kind="secondary"] {{
  border: 1.5px solid #B9CFC3 !important;
  color: #10221B !important;
  background: #fff !important;
}}
.stButton > button[kind="primary"] {{
  background: #0E6B54 !important;
}}
section[data-testid="stSidebar"] .stLinkButton > a,
section[data-testid="stSidebar"] a[data-testid="stBaseLinkButton"] {{
  border-radius: 10px !important;
}}
.ww-card {{
  margin: 0.55rem 0 0.2rem 0;
  padding: 0.85rem 1rem 0.5rem 1rem;
  border: 1px solid #DCE9E1;
  background: #FFFFFF;
  border-radius: 18px;
}}
.ww-card-title {{
  margin: 0 0 0.25rem 0 !important;
  font-size: 1.02rem;
  color: #10221B;
  line-height: 1.3;
}}
div[data-testid="stChatMessage"] {{
  border-radius: 18px !important;
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
/* Sticky category bar  -  only the keyed container (NOT :has(), which
   matched parent blocks and covered the page, eating the first click). */
div.st-key-ww_cat_bar {{
  position: sticky !important;
  top: 0 !important;
  z-index: 120 !important;
  background: rgba(241, 247, 243, 0.96) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 0.55rem 0.35rem 0.65rem 0.35rem !important;
  margin: 0 0 0.35rem 0 !important;
  border-bottom: 1px solid #D3E3DA;
  box-shadow: 0 4px 12px rgba(16, 34, 27, 0.05);
}}
/* Yelp card action row  -  equal-height pills */
div[data-testid="stHorizontalBlock"] .stButton > button {{
  white-space: nowrap !important;
}}
/* Room for ChatGPT-style prompt rail on the right */
.main .block-container {{
  padding-right: 3.25rem !important;
}}
.ww-prompt-anchor {{
  height: 0;
  width: 0;
  overflow: hidden;
  scroll-margin-top: 96px;
}}
div[class*="st-key-ww_masonry_"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {{
  align-items: flex-start;
  gap: 1rem;
}}
div[class*="st-key-ww_result_view_"] [data-testid="stSegmentedControl"] {{
  margin-bottom: 0.35rem;
}}
@media (max-width: 760px) {{
  .main .block-container {{
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
  }}
  .ww-hero {{
    border-radius: 18px;
    padding: 1rem 1.1rem;
  }}
  div[class*="st-key-ww_masonry_"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {{
    flex-direction: column;
  }}
  div[class*="st-key-ww_masonry_"] > div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
    width: 100% !important;
    flex: 1 1 100% !important;
  }}
  div[class*="st-key-ww_card_actions_"] div[data-testid="stHorizontalBlock"] {{
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.4rem !important;
  }}
  div[class*="st-key-ww_card_actions_"] div[data-testid="stColumn"] {{
    width: calc(33.333% - 0.3rem) !important;
    min-width: 0 !important;
    max-width: calc(33.333% - 0.3rem) !important;
    flex: 1 1 calc(33.333% - 0.3rem) !important;
  }}
  div[class*="st-key-ww_card_actions_"] .stButton > button {{
    min-height: 42px !important;
    padding-left: 0.35rem !important;
    padding-right: 0.35rem !important;
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }}
}}
</style>
<div class="ww-hero">
  <div class="ww-brand-lockup">
    <svg class="ww-route-mark" viewBox="0 0 44 44" fill="none" aria-hidden="true">
      <path d="M6 11 L14 33 L22 17 L30 33 L38 11" stroke="#F1F7F3" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
      <circle cx="38" cy="11" r="4.5" fill="#7FD3A8"></circle>
    </svg>
    <p class="ww-brand">{i18n.t("brand", _ui_lang0)}</p>
  </div>
  <p class="ww-tag">{i18n.t("tagline", _ui_lang0)}</p>
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

import importlib
import core.spellcheck as spellcheck

# Streamlit keeps sys.modules across reruns: pick up new helpers after edits
if not hasattr(spellcheck, "is_paginate_command") or not hasattr(spellcheck, "is_ui_command"):
    spellcheck = importlib.reload(spellcheck)


def _is_paginate_command(text: str) -> bool:
    """Paginate ('more'), resilient if Streamlit holds a stale spellcheck module."""
    fn = getattr(spellcheck, "is_paginate_command", None)
    if callable(fn):
        return bool(fn(text))
    q = (text or "").strip().lower()
    return q in {"more", "next", "again", "show more", "more results", "show more results"}


def _is_ui_command(text: str) -> bool:
    fn = getattr(spellcheck, "is_ui_command", None)
    if callable(fn):
        return bool(fn(text))
    return _is_paginate_command(text) or (text or "").strip().lower() in {"yes", "no", "ok", "okay"}

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

    # Any 4–5 digit run  -  resolve via similarity to known ZIPs (handles typos)
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
    # If the ZIP ended a location phrase, remove its stranded connector so
    # the result intro does not say "near near 60629".
    cleaned = re.sub(r"\b(?:near|around|in|by|close\s+to)\s*$", "", cleaned, flags=re.I)
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
    """Preferred service cues  -  used as soft boosts, not hard gates."""
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
    """Substring or prefix hit  -  leeway for short / partial words."""
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
    not hard gates  -  so near-misses still surface. Fuzzy score adds typo leeway.
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
                day_ok = False  # missing hours  -  still keep in soft mode
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

        # Fuzzy leeway  -  for short queries, score against NAME only (avoid junk hits)
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
    Hidden until 2+ user prompts; one mark per turn; grows as the chat grows.
    Always clears a stale rail left in the parent DOM from earlier runs.
    """
    import json
    import streamlit.components.v1 as components

    # Always remove a leftover rail when we don't want one (0–1 prompts).
    if len(prompts) < 2:
        components.html(
            """
<!DOCTYPE html><html><body><script>
(function () {
  try {
    const doc = window.parent.document;
    doc.querySelectorAll(".ww-prompt-rail").forEach((el) => el.remove());
  } catch (e) {}
})();
</script></body></html>
""",
            height=0,
            width=0,
        )
        return

    items = [
        {"id": f"ww-prompt-{idx}", "title": _prompt_preview(txt), "n": i + 1}
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

  doc.querySelectorAll(".ww-prompt-rail").forEach((el) => el.remove());

  let style = doc.getElementById("ww-prompt-rail-css");
  if (!style) {{
    style = doc.createElement("style");
    style.id = "ww-prompt-rail-css";
    doc.head.appendChild(style);
  }}
  style.textContent = `
      .ww-prompt-rail {{
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
        box-shadow: 0 4px 18px rgba(16, 34, 27, 0.08);
        border: 1px solid #DCE9E1;
      }}
      .ww-prompt-rail button.ww-tick {{
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
      .ww-prompt-rail button.ww-tick:hover {{
        background: rgba(14, 107, 84, 0.55);
        width: 24px;
      }}
      .ww-prompt-rail button.ww-tick.active {{
        background: #0E6B54;
        width: 26px;
        box-shadow: 0 0 0 3px rgba(14, 107, 84, 0.22);
      }}
      @media (max-width: 768px) {{
        .ww-prompt-rail {{ right: 6px; padding: 10px 6px; gap: 8px; }}
        .ww-prompt-rail button.ww-tick {{ width: 14px; }}
        .ww-prompt-rail button.ww-tick.active {{ width: 20px; }}
      }}
    `;

  const rail = doc.createElement("nav");
  rail.className = "ww-prompt-rail";
  rail.setAttribute("aria-label", "Jump to earlier prompts");

  function setActive(id) {{
    rail.querySelectorAll("button.ww-tick").forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.target === id);
    }});
  }}

  items.forEach((item, i) => {{
    const btn = doc.createElement("button");
    btn.type = "button";
    btn.className = "ww-tick" + (i === items.length - 1 ? " active" : "");
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
        from core.labels import humanize_service_label

        t = humanize_service_label(t or "")
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
    parsed = [p.strip(" .") for p in re.split(r"[,;|•·]", stxt) if p.strip(" .")]
    for part in parsed:
        add(part)

    if not parsed:
        services = item.get("services") or []
        if isinstance(services, list):
            for s in services:
                add(str(s))
        elif services:
            add(str(services))

    for badge in item.get("availability_badges") or []:
        add(str(badge))

    return tags



# Inline stroke icons for result-card facts. The design system retires emoji as
# UI glyphs: they render inconsistently across platforms, are announced as their
# CLDR name by screen readers ("round pushpin"), and cannot inherit text colour.
_ICON = {
    "pin": '<path d="M10 17.5s5.5-4.8 5.5-9a5.5 5.5 0 1 0-11 0c0 4.2 5.5 9 5.5 9Z"/><circle cx="10" cy="8.5" r="2"/>',
    "phone": '<path d="M6.2 3.5h2.1l1.1 3-1.5 1.1a9 9 0 0 0 4.5 4.5l1.1-1.5 3 1.1v2.1c0 .8-.7 1.4-1.5 1.3C8.4 14.5 5.5 11.6 4.9 5A1.4 1.4 0 0 1 6.2 3.5Z"/>',
    "link": '<path d="M8.5 11.5a3 3 0 0 0 4.2 0l2.1-2.1a3 3 0 0 0-4.2-4.2l-1 1"/><path d="M11.5 8.5a3 3 0 0 0-4.2 0l-2.1 2.1a3 3 0 0 0 4.2 4.2l1-1"/>',
    "speech": '<path d="M16.5 11.5a2 2 0 0 1-2 2H8l-3.5 3v-3a2 2 0 0 1-1-1.7V5.5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2Z"/>',
    "clock": '<circle cx="10" cy="10" r="6.5"/><path d="M10 6.3V10l2.5 1.6"/>',
}


def _icon(name: str) -> str:
    """A 16px stroke icon that inherits the surrounding text colour."""
    return (
        '<svg class="yelp-ico" width="16" height="16" viewBox="0 0 20 20" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">' + _ICON[name] + "</svg>"
    )


def render_card(idx: int, item: Dict, cat_key: str, user_need: str = "", key_suffix: str = ""):
    """Yelp-style listing  -  ≤4 specialty chips (+▾); Details / Pin / Map / Comments."""
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

    visible = tags[:2]
    extra = tags[2:]
    chips = "".join(f'<span class="yelp-chip">{html_escape(t)}</span>' for t in visible)
    if extra:
        chips += f'<span class="yelp-chip yelp-chip-count">+{len(extra)}</span>'

    # Phone / website  -  always show (Yelp-style contact lines)
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
        facts.append(f'<div class="yelp-fact">{_icon("pin")}<span>{html_escape(addr)}</span></div>')
    if phone:
        tel = re.sub(r"\D", "", phone)
        if len(tel) >= 10:
            facts.append(
                f'<div class="yelp-fact">{_icon("phone")}<a href="tel:{html_escape(tel)}">{html_escape(phone)}</a></div>'
            )
        else:
            facts.append(f'<div class="yelp-fact">{_icon("phone")}<span>{html_escape(phone)}</span></div>')
    else:
        facts.append(f'<div class="yelp-fact yelp-fact-muted">{_icon("phone")}<span>Phone not listed</span></div>')
    if website:
        facts.append(
            f'<div class="yelp-fact">{_icon("link")}<a href="{html_escape(website)}" target="_blank" '
            f'rel="noopener noreferrer">{html_escape(i18n.t("website_label", _cl))}</a></div>'
        )
    else:
        facts.append(f'<div class="yelp-fact yelp-fact-muted">{_icon("link")}<span>Website not listed</span></div>')
    if lang_str:
        facts.append(f'<div class="yelp-fact">{_icon("speech")}<span>{html_escape(lang_str)}</span></div>')
    if hours_str:
        facts.append(f'<div class="yelp-fact">{_icon("clock")}<span>{html_escape(hours_str)}</span></div>')
    facts_html = "".join(facts)

    # on_click + early switch_page (see session init) = one click navigation.
    # Mid-script switch_page / changing pin keys caused a “need 2 presses” feel.
    _rid = str(item["id"])

    def _go_detail():
        st.session_state["current_resource_id"] = _rid
        st.session_state["current_category"] = cat_key
        st.session_state["scroll_to_comments"] = False
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
  border-radius: 18px;
  padding: 1rem 1rem 0.4rem 1rem;
  margin: 0 0 0.35rem 0;
  box-shadow: 0 0 0 1px rgba(16,34,27,.07), 0 2px 8px rgba(16,34,27,.05);
  font-family: 'DM Sans', system-ui, sans-serif;
}}
.yelp-card-head {{ display: flex; gap: 0.75rem; align-items: flex-start; }}
.yelp-idx {{
  flex-shrink: 0; width: 1.6rem; height: 1.6rem;
  border-radius: 6px; background: #0E6B54; color: #fff;
  font-weight: 700; font-size: 0.85rem;
  display: flex; align-items: center; justify-content: center;
  margin-top: 0.1rem;
}}
.yelp-name {{
  margin: 0 0 0.4rem 0; font-size: 1.08rem; font-weight: 700; color: #10221B; line-height: 1.3;
}}
.yelp-chips {{ display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.45rem; align-items: center; }}
.yelp-chip {{
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.72rem; font-weight: 600;
  padding: 0.2rem 0.55rem; border-radius: 999px;
  background: #D6EBE0; color: #08432F; border: 1px solid #CFE6DA;
  line-height: 1.2; box-sizing: border-box;
}}
.yelp-chip.yelp-open {{ background: #10b981; color: #fff; border-color: #10b981; }}
.yelp-chip-count {{ background: transparent; border-color: #B9CFC3; color: #4A5F55; }}
.yelp-facts {{ margin: 0.15rem 0 0.35rem 0; }}
.yelp-fact {{
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  font-size: 0.86rem; color: #4a5f56; line-height: 1.45; margin: 0.12rem 0;
}}
.yelp-fact-muted {{ color: #4A5F55; font-style: italic; }}
.yelp-ico {{ flex: 0 0 auto; margin-top: 0.15rem; color: #4A5F55; }}
.yelp-fact a {{ color: #0A4B3A; font-weight: 600; text-decoration: none; }}
.yelp-fact a:hover {{ text-decoration: underline; }}
</style>
""",
            unsafe_allow_html=True,
        )

        # Three compact actions. Comments live on the Details page.
        actions = st.container(key=f"ww_card_actions_{uid}")
        c_details, c_pin, c_map = actions.columns(3, gap="small")

        with c_details:
            st.button(
                i18n.t("details_short", _cl),
                key=f"detail_{uid}",
                use_container_width=True,
                on_click=_go_detail,
                icon=":material/info:",
            )

        with c_pin:
            pinned_now = is_pinned(cat_key, item["id"])
            st.button(
                i18n.t("unpin" if pinned_now else "pin", _cl),
                key=f"pin_{uid}",
                use_container_width=True,
                on_click=_do_pin,
                icon=":material/bookmark:" if pinned_now else ":material/bookmark_add:",
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
                    icon=":material/map:",
                )



def render_results_block(results: List[Dict], category: str, intro: str = "", block_id: str = "main"):
    """Render a balanced card grid or one map for the current result set."""
    import map_utils

    if intro:
        mascot.pip_say(intro)

    with st.container(key=f"ww_result_view_{block_id}"):
        view = st.segmented_control(
            "View results",
            options=("cards", "map"),
            default="cards",
            format_func=lambda option: (
                i18n.t("view_cards", st.session_state.get("ui_lang_code", "en"))
                if option == "cards"
                else i18n.t("map_short", st.session_state.get("ui_lang_code", "en"))
            ),
            key=f"result_view_{block_id}",
            label_visibility="collapsed",
            width="stretch",
        )

    if view == "map":
        map_utils.render_map_view(results, category=category)
    else:
        # Two columns preserve usable action targets; estimated content weight
        # keeps longer cards from collecting in a single column.
        with st.container(key=f"ww_masonry_{block_id}"):
            columns = st.columns(2, gap="medium")
            weights = [0, 0]
            for i, card in enumerate(results, 1):
                tags = _specialty_tags(card, category)
                weight = 4 + min(len(tags), 3)
                if card.get("languages"):
                    weight += 1
                if card.get("hours_text") or card.get("hours"):
                    weight += 1
                column_index = weights.index(min(weights))
                weights[column_index] += weight
                with columns[column_index]:
                    render_card(i, card, category, key_suffix=f"_{block_id}")
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
st.session_state.setdefault("ww_smart_llm", False)

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
# Sidebar  -  Language → Account → Forms → Saved → Filters
# ===========================
ui_lang = _ui_lang0

with st.sidebar:
    # Account + status (language already rendered above hero)
    with st.expander(i18n.t("auth", ui_lang), expanded=False):
        auth.render_auth_sidebar(ui_lang)
        status = llm_service.llm_status()
        if status["available"]:
            st.success(f"{i18n.t('ai_online', ui_lang)} · {status['provider']}")
        elif status.get("configured_provider") in {
            "workers_ai",
            "cloudflare",
            "cloudflare_workers_ai",
        }:
            st.warning(i18n.t("ai_offline", ui_lang).split("  -  ")[0])
            st.caption("Add the Cloudflare Workers AI account ID and token.")
        elif status.get("configured_provider") in {"none", "off", "disabled"}:
            st.caption("Smart answers are disabled. Search remains available.")
        else:
            st.warning(i18n.t("ai_offline", ui_lang))
            st.caption(i18n.t("ollama_hint", ui_lang))
        st.caption(i18n.t("whatsapp_hint", ui_lang))

    # Voice  -  Pip speaks replies (free browser TTS)
    import core.voice as voice

    st.markdown('<hr class="ww-side-rule"/>', unsafe_allow_html=True)
    voice.render_voice_toggle(ui_lang)
    st.toggle(
        "Smarter answers (slower)",
        key="ww_smart_llm",
        help="Uses local Ollama for understanding  -  slower. Off = fast search.",
    )
    st.markdown('<hr class="ww-side-rule"/>', unsafe_allow_html=True)

    # Forms
    import core.forms as forms

    with st.expander(i18n.t("forms_section", ui_lang), expanded=True):
        st.markdown(f'<p class="ww-side-title">{i18n.t("forms_users", ui_lang)}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="ww-side-cap">{i18n.t("forms_users_cap", ui_lang)}</p>', unsafe_allow_html=True)
        st.link_button(
            i18n.t("forms_users_btn", ui_lang),
            forms.community_report_url(),
            use_container_width=True,
        )
        st.markdown("")
        st.markdown(f'<p class="ww-side-title">{i18n.t("forms_clinics", ui_lang)}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="ww-side-cap">{i18n.t("forms_clinics_cap", ui_lang)}</p>', unsafe_allow_html=True)
        st.link_button(
            i18n.t("forms_clinics_btn", ui_lang),
            forms.clinic_update_url(),
            use_container_width=True,
        )

    # 4) Saved  -  always open the place website (external), never a chat page
    with st.expander(i18n.t("pinned", ui_lang), expanded=False):
        if st.session_state["pinned"]:
            for i, p in enumerate(st.session_state["pinned"], 1):
                name = p.get("name") or "Saved place"
                website = (p.get("website") or "").strip()
                if website:
                    st.link_button(f"{i}. {name}", website, use_container_width=True)
                else:
                    st.caption(f"{i}. {name}  -  no website listed")
        else:
            st.caption(i18n.t("pinned_empty", ui_lang))

    # 5) Recent (optional)
    with st.expander(i18n.t("recent", ui_lang), expanded=False):
        try:
            search_helpers.render_recent_searches(st.session_state["category"])
        except Exception:
            st.caption(" - ")

    st.markdown('<hr class="ww-side-rule"/>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="ww-side-title">{i18n.t("filters", ui_lang)}</p>',
        unsafe_allow_html=True,
    )

# ===========================
# Category  -  sticky “What do you need?” bar
# ===========================
_ui_lang = st.session_state.get("ui_lang_code", "en")
with st.container(key="ww_cat_bar"):
    st.markdown(
        f"<p class='ww-cat-label'>{i18n.t('category_label', _ui_lang)}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<style>
.ww-cat-label {
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: 1.05rem; font-weight: 700; color: #10221B;
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
# Midwest states available in the expanded resource set (State filter → ZIP unlock)
UI_FILTER_STATES = ("IL", "IN")
STATE_LABELS = {"IL": "Illinois (IL)", "IN": "Indiana (IN)"}

def get_dataset(cat_key: str, state: Optional[str] = None) -> Tuple[List[Dict], str]:
    """Load dataset using data_loader.py for structured JSON data (per state)."""
    st_code = (state or st.session_state.get("filter_state") or "IL").strip().upper() or "IL"
    try:
        items = data_loader.load_category_data(cat_key, state=st_code)

        cache_key = f"{cat_key}::{st_code}"
        if cache_key not in st.session_state.get("raw_text_cache", {}):
            raw_text_parts = []
            for item in items[:200]:
                raw_text_parts.append(
                    f"{item.get('name', '')} {item.get('address', '')} "
                    f"{item.get('services_text', '')} {item.get('languages', '')}"
                )
            raw_text = "\n".join(raw_text_parts)
            st.session_state.setdefault("raw_text_cache", {})[cache_key] = raw_text
        else:
            raw_text = st.session_state["raw_text_cache"][cache_key]

        return items, raw_text
    except Exception as e:
        st.warning(f"⚠️ Using fallback parsing (data_loader failed: {e})")
        if cat_key in st.session_state.get("datasets_cache", {}):
            return st.session_state["datasets_cache"][cat_key]
        text = fetch_text_from_sources(DATA_SOURCES[cat_key])
        items = parse_blocks(text)
        st.session_state.setdefault("datasets_cache", {})[cat_key] = (items, text)
        return items, text

st.session_state.setdefault("filter_state", "")

_boot_state = st.session_state.get("filter_state") or "IL"
try:
    items, raw_text = get_dataset(st.session_state["category"], _boot_state)
except Exception as e:
    st.error(f"⚠️ Could not load the **{st.session_state['category']}** dataset. Check the GitHub/raw path or local fallback.\n\n{e}")
    st.stop()

# Build filter options from the loaded dataset (any US ZIP in this state's listings)
def _item_zips(dataset: List[Dict]) -> List[str]:
    found = set()
    for it in dataset or []:
        z = str(it.get("zip_code") or it.get("zip") or "").strip()
        m = re.search(r"\b(\d{5})\b", z)
        if m:
            found.add(m.group(1))
            continue
        addr = it.get("address") or ""
        for zm in re.finditer(r"\b(\d{5})\b", addr):
            found.add(zm.group(1))
    return sorted(found)

all_zips = _item_zips(items)
if not all_zips and raw_text:
    all_zips = sorted(set(re.findall(r"\b\d{5}\b", raw_text)))
lang_lines = re.findall(r"🗣\s*Languages:\s*(.+)", raw_text)
langs = set()
for line in lang_lines:
    for lang in re.split(r"[;,]", line):
        lang = lang.strip()
        if lang and not lang.lower().startswith("and"):
            langs.add(lang)
# Prefer structured language fields when present
for it in items or []:
    for lang in it.get("languages") or []:
        if isinstance(lang, str) and lang.strip():
            langs.add(lang.strip())
    lt = it.get("languages_text") or ""
    for part in re.split(r"[;,]", lt):
        part = part.strip()
        if part:
            langs.add(part)
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
    _state_placeholder = i18n.t("filter_state_placeholder", _ui_lang)

    prev_state = st.session_state.get("filter_state") or ""
    state_options = [""] + list(UI_FILTER_STATES)
    state_filter = st.selectbox(
        i18n.t("filter_state", _ui_lang),
        state_options,
        index=state_options.index(prev_state) if prev_state in state_options else 0,
        format_func=lambda x: _state_placeholder if not x else STATE_LABELS.get(x, x),
        key="filter_state_select",
    )
    if state_filter != prev_state:
        st.session_state["filter_state"] = state_filter
        # Drop stale ZIP when the state changes
        for zip_key in (f"zip_{cat_choice}", f"zip_{cat_choice}_locked"):
            if zip_key in st.session_state:
                del st.session_state[zip_key]
        st.rerun()

    st.session_state["filter_state"] = state_filter

    # ZIP unlocked only after a state is chosen
    zip_enabled = bool(state_filter)
    if zip_enabled:
        # Reload items for the selected state so ZIP list matches
        try:
            items, raw_text = get_dataset(st.session_state["category"], state_filter)
            all_zips = _item_zips(items)
        except Exception:
            pass
        zip_opts = ["All"] + all_zips
        zip_filter = st.selectbox(
            i18n.t("filter_zip", _ui_lang),
            zip_opts,
            format_func=lambda x: _all if x == "All" else x,
            key=f"zip_{cat_choice}",
        )
    else:
        st.selectbox(
            i18n.t("filter_zip", _ui_lang),
            ["All"],
            format_func=lambda x: _all if x == "All" else x,
            key=f"zip_{cat_choice}_locked",
            disabled=True,
        )
        st.caption(i18n.t("filter_zip_locked", _ui_lang))
        zip_filter = "All"

    lang_opts = ["All"] + all_langs
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
    
    neighborhoods = neighborhood_mapping.get_all_neighborhoods() if state_filter == "IL" else []
    if neighborhoods:
        st.caption(i18n.t("tip_neighborhood", _ui_lang))
    
    # QR Code section removed - not necessary
    st.markdown(
        """
<style>
/* Matching Reset / Scroll pills, full width, centered label */
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton {
  width: 100% !important;
}
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button {
  width: 100% !important;
  min-height: 2.5rem !important;
  white-space: nowrap !important;
  border: 2px solid #0E6B54 !important;
  border-radius: 999px !important;
  background: #ffffff !important;
  color: #10221B !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  padding: 0.4rem 0.75rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button > div,
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button > div > p,
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button p {
  width: 100% !important;
  margin: 0 !important;
  text-align: center !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}
section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button:hover {
  background: #eef7f2 !important;
  border-color: #0E6B54 !important;
  color: #10221B !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button(i18n.t("reset", _ui_lang), key="reset_chat", use_container_width=True):
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
        if st.button(i18n.t("scroll_latest", _ui_lang), key="scroll_latest_btn", use_container_width=True):
            import streamlit.components.v1 as components

            components.html(
                """
<!DOCTYPE html><html><body><script>
(function () {
  try {
    const doc = window.parent.document;
    const el = doc.getElementById("bottom");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "end" });
  } catch (e) {}
})();
</script></body></html>
""",
                height=0,
                width=0,
            )



# ===========================
# Response function definition
# ===========================
def respond_to_query(user_text: str, category: str):
    is_more = _is_paginate_command(user_text)
    
    # Get conversation context for follow-up handling
    context = llm_service.get_conversation_context()
    context.add_user_message(user_text)

    # 1) Load dataset first (required before using items)
    items, _ = get_dataset(category, st.session_state.get("filter_state") or "IL")
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
    use_smart = st.session_state.get("ww_smart_llm", False)

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
                        # No st.chat_message  -  avoids Streamlit’s orange robot avatar
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

    # Grounded hybrid retrieval is the final ordering layer. The legacy ranker
    # above still computes UI annotations such as open-now and nearby-ZIP tiers;
    # Ollama embeddings improve recall without becoming a source of records.
    if ranked:
        hybrid = retrieve_resources(
            [item for _, item in ranked],
            query,
            limit=len(ranked),
            state=st.session_state.get("filter_state") or "IL",
            language=None if lf == "All" else lf,
            zip_code=None if zf == "All" else zf,
            service=None if sf == "All" else sf,
            use_semantic=True,
        )
        if hybrid.items:
            ranked = [
                (float(len(hybrid.items) - index), item)
                for index, item in enumerate(hybrid.items)
            ]
        st.session_state["last_retrieval_mode"] = hybrid.mode
        st.session_state["last_retrieval_source_ids"] = hybrid.source_ids

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

    # 5) Assistant reply  -  Pip via pip_say only (no chat_message = no orange robot)
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
                f"\n\n📍 No exact listings in **{zf}**  -  showing nearby ZIP areas instead."
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
                "That’s everything I found for this search. Try a different ZIP, service, or neighborhood  -  or tap a suggestion below."
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
# Chat input + spell check (single input  -  chat bar only)
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
        # No chat_message wrapper  -  Pip comes from pip_say only (no orange robot)
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
                f'<div id="ww-prompt-{mi}" class="ww-prompt-anchor"></div>',
                unsafe_allow_html=True,
            )
        avatar = mascot.PIP_AVATAR if msg["role"] == "assistant" else mascot.USER_AVATAR
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg.get("text", ""))

# Pending spell confirmation UI (from chat_input path)
_pending_spell = st.session_state.get("pending_spell_check")
if _pending_spell and isinstance(_pending_spell, dict):
    with st.chat_message("assistant", avatar=mascot.PIP_AVATAR):
        fixes = _pending_spell.get("fixes") or []
        bits = ", ".join(f"**{b}** → **{g}**" for b, g in fixes)
        st.info(f"✏️ Before I search - spelling check: {bits}")
        st.markdown(f"Corrected search: **{_pending_spell.get('corrected')}**")
        st.markdown(
            """
<style>
div[data-testid="stChatMessage"] div[data-testid="stHorizontalBlock"] .stButton > button {
  white-space: nowrap !important;
  border: 2px solid #0E6B54 !important;
  border-radius: 999px !important;
  background: #ffffff !important;
  color: #10221B !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
}
div[data-testid="stChatMessage"] div[data-testid="stHorizontalBlock"] .stButton > button p,
div[data-testid="stChatMessage"] div[data-testid="stHorizontalBlock"] .stButton > button > div {
  width: 100% !important;
  margin: 0 !important;
  text-align: center !important;
  justify-content: center !important;
}
</style>
""",
            unsafe_allow_html=True,
        )
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
    # "Type more" / pagination commands must never hit the spelling gate
    spell = (
        {"flagged": False}
        if _is_ui_command(prompt)
        else spellcheck.check_query(prompt)
    )
    if spell.get("flagged") and not st.session_state.get("_spell_bypass"):
        # Flag before searching - wait for Use corrected / Keep my spelling
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
            f'<div id="ww-prompt-{_new_mi}" class="ww-prompt-anchor"></div>',
            unsafe_allow_html=True,
        )
        with st.chat_message("user", avatar=mascot.USER_AVATAR):
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
