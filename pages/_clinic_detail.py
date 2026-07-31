#!/usr/bin/env python3
"""
Clinic/Resource Detail Page
Shows detailed information about a resource and includes discussion section.
"""

import streamlit as st
import urllib.parse
import json
from pathlib import Path

# Import modules
import database as db
import auth
import comments
import data_loader
import search

# ===========================
# Page Configuration
# ===========================
st.set_page_config(
    page_title="Resource Details",
    page_icon="🏥",
    layout="wide"
)

# Initialize database (soft — page still works offline)
try:
    db.initialize_database()
except Exception:
    pass

# Initialize auth
auth.init_session_state()

# ===========================
# Helper Functions
# ===========================

def get_resource_by_id(resource_id: str, category: str) -> dict:
    """Load a specific resource by ID and category (local JSON first)."""
    try:
        items = data_loader.load_category_data(category, force_refresh=False)
        if not items:
            return None
        
        search_id = str(resource_id).strip()
        for item in items:
            item_id = str(item.get("id", "")).strip()
            if item_id == search_id:
                return item
        
        for item in items:
            item_id = str(item.get("id", "")).strip()
            if item_id.lstrip("0") == search_id.lstrip("0"):
                return item
        
    except Exception as e:
        st.error(f"Error loading resource: {e}")
    return None

def get_category_emoji(category: str) -> str:
    """Get emoji for a category."""
    if "health" in category.lower():
        return "🏥"
    elif "education" in category.lower():
        return "🎓"
    else:
        return "🏠"


def get_verification_label(resource: dict, category: str) -> str:
    """Most recent verification / listing update date for the detail page."""
    from datetime import datetime
    from pathlib import Path

    raw = (
        resource.get("verified_at")
        or resource.get("last_verified")
        or resource.get("verification_date")
        or resource.get("updated_at")
    )
    if raw:
        try:
            if isinstance(raw, (int, float)):
                return datetime.utcfromtimestamp(raw).strftime("%b %d, %Y")
            s = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s[:19]) if "T" in s else datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.strftime("%b %d, %Y")
        except Exception:
            return str(raw)[:16]

    # Fallback: category JSON file mtime on disk
    cat = (category or "").lower()
    if "health" in cat:
        fname = "healthcare.json"
    elif "education" in cat:
        fname = "education.json"
    else:
        fname = "resettlement_legal_shelter.json"
    path = Path(__file__).resolve().parent.parent / "data" / fname
    try:
        if path.exists():
            return datetime.fromtimestamp(path.stat().st_mtime).strftime("%b %d, %Y")
    except Exception:
        pass
    return "Unknown"


def specialty_chips_for_resource(resource: dict) -> list:
    """Deduped specialty labels for the detail page (same idea as search cards)."""
    import re

    tags = []
    seen = set()

    def add(t: str):
        t = (t or "").strip()
        if not t:
            return
        key = re.sub(r"[^a-z0-9]+", "", t.lower())
        if not key or key in seen:
            return
        seen.add(key)
        tags.append(t)

    for s in resource.get("subcategories") or []:
        add(str(s))

    blob = " ".join(
        [
            str(resource.get("services_text") or ""),
            str(resource.get("search_blob") or ""),
            str(resource.get("notes") or ""),
        ]
    ).lower()
    if re.search(r"ryan\s*white|hrsa\s*hab", blob):
        # Ensure program context appears even if subcategory parse missed it
        if "Ryan White HIV/AIDS Program" not in tags:
            tags.insert(0, "Ryan White HIV/AIDS Program")
            seen.add(re.sub(r"[^a-z0-9]+", "", "Ryan White HIV/AIDS Program".lower()))

    stxt = resource.get("services_text") or ""
    stxt = re.sub(r"^.*?Services:\s*", "", str(stxt), flags=re.I).replace("🏥", "").strip()
    parts = [p.strip(" .") for p in re.split(r"[;|•·]", stxt) if p.strip(" .")]
    for p in parts:
        add(p)
    if not parts:
        for s in resource.get("services") or []:
            add(str(s).replace("_", " ").title())
    for b in resource.get("availability_badges") or []:
        add(str(b))
    return tags



def to_12h(time_str: str) -> str:
    """Convert 'HH:MM' 24-hour string to 12-hour with am/pm."""
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        suffix = "am"

        if hour == 0 or hour == 24:
            display_hour = 12
            suffix = "am"
        elif hour == 12:
            display_hour = 12
            suffix = "pm"
        elif hour > 12:
            display_hour = hour - 12
            suffix = "pm"
        else:
            display_hour = hour
            suffix = "am"

        return f"{display_hour}:{minute:02d} {suffix}"
    except Exception:
        return time_str


def normalize_hours(day_ranges: list) -> list:
    """
    Clean and deduplicate time ranges for a single day.
    Drops invalid or overlapping/duplicate ranges that commonly appear
    when parsing mixed-format hours text.
    """
    if not day_ranges:
        return []

    cleaned = []
    for rng in day_ranges:
        if not rng or len(rng) != 2:
            continue
        start, end = rng
        if not (isinstance(start, (list, tuple)) and isinstance(end, (list, tuple))):
            continue
        if len(start) != 2 or len(end) != 2:
            continue

        sh, sm = int(start[0]), int(start[1])
        eh, em = int(end[0]), int(end[1])

        start_minutes = sh * 60 + sm
        end_minutes = eh * 60 + em

        # Handle cases where parser produced end at "00" (often 12 PM/AM confusion)
        # If end is midnight and start is daytime, treat as 24:00 for same-day display.
        if end_minutes == 0 and start_minutes >= 8 * 60:
            end_minutes = 24 * 60

        # Drop if end <= start (invalid) or if duration is excessively long (>18h)
        duration = end_minutes - start_minutes
        if duration <= 0 or duration > 18 * 60:
            continue

        cleaned.append((start_minutes, end_minutes))

    # Deduplicate and sort
    cleaned = sorted(set(cleaned))

    # Merge overlaps
    merged = []
    for rng in cleaned:
        if not merged:
            merged.append(rng)
            continue
        prev_start, prev_end = merged[-1]
        cur_start, cur_end = rng
        if cur_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append(rng)

    # Convert back to hour/min tuples
    def to_hm(total_minutes):
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h:02d}:{m:02d}"

    return [(to_hm(s), to_hm(e)) for s, e in merged]

# ===========================
# Main Page
# ===========================

def render_detail_page():
    """Render the resource detail page."""
    
    # Get parameters from URL - handle both single values and lists
    params = st.query_params
    
    # Helper to extract single value from query params
    def get_param(key, default=None):
        value = params.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value if value else default
    
    # Prefer session (set by Details button) then URL params
    resource_id = (
        st.session_state.get("current_resource_id")
        or get_param("id")
    )
    category = (
        st.session_state.get("current_category")
        or get_param("category")
    )
    if resource_id:
        st.session_state["current_resource_id"] = str(resource_id)
    if category:
        st.session_state["current_category"] = str(category)

    if not resource_id or not category:
        st.warning("⚠️ No resource selected.")
        st.markdown("Please select a resource from the search results.")
        st.info("💡 Click '📋 View Details' on any search result card to view its details.")
        
        # Link back to main page
        if st.button("← Back to Search"):
            st.switch_page("Aidr.py")
        return
    
    # Load the resource
    try:
        with st.spinner("Loading resource details..."):
            resource = get_resource_by_id(str(resource_id), str(category))
            # Persist for reruns (e.g., after posting a comment)
            st.session_state["current_resource_id"] = str(resource_id)
            st.session_state["current_category"] = str(category)
    except Exception as e:
        st.error(f"❌ Error loading resource: {e}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())
        if st.button("← Back to Search"):
            st.switch_page("Aidr.py")
        return
    
    if not resource:
        st.error(f"❌ Resource not found")
        st.markdown(f"""
        **Details:**
        - Resource ID: `{resource_id}`
        - Category: `{category}`
        
        💡 The resource may have been removed or the ID is incorrect.
        """)
        
        # Show available categories
        st.info("💡 Try selecting a resource from the search results on the main page.")
        if st.button("← Back to Search"):
            st.switch_page("Aidr.py")
        return
    
    # ===========================
    # Yelp-style detail layout
    # ===========================
    import re
    import html as html_mod
    import core.forms as forms
    from data_loader import normalize_address
    import map_utils

    def esc(s: str) -> str:
        return html_mod.escape(str(s or ""))

    name = resource.get("name") or "Unknown"
    address = normalize_address(resource.get("address") or "")
    phone = re.sub(r"^📞\s*", "", (resource.get("phone") or "").strip())
    phone_digits = (resource.get("phone_digits") or "").strip() or re.sub(r"\D", "", phone)
    website = re.sub(r"^🌐\s*", "", (resource.get("website") or "").strip())
    chips = specialty_chips_for_resource(resource)
    verified = get_verification_label(resource, str(category))

    notes = (resource.get("notes") or "")
    is_ryan_white = bool(
        re.search(
            r"ryan\s*white|hrsa\s*hab",
            " ".join(
                [
                    notes,
                    str(resource.get("services_text") or ""),
                    str(resource.get("search_blob") or ""),
                    " ".join(resource.get("subcategories") or []),
                ]
            ),
            re.I,
        )
    )
    langs = resource.get("languages") or []
    if isinstance(langs, list):
        lang_str = ", ".join(str(l) for l in langs)
    else:
        lang_str = str(langs)

    hours_text = resource.get("hours_text")
    hours_dict = resource.get("hours")
    is_open = search.is_open_now(resource)
    open_chip = '<span class="yelp-chip yelp-open">Open now</span>' if is_open else ""
    chips_html = "".join(f'<span class="yelp-chip">{esc(c)}</span>' for c in chips)

    # Hours rows for schedule card
    hours_rows_html = ""
    if hours_dict and isinstance(hours_dict, dict):
        days_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days_order:
            if day in hours_dict and hours_dict[day]:
                normalized = normalize_hours(hours_dict[day])
                times_str = [f"{to_12h(s)} – {to_12h(e)}" for s, e in normalized]
                if times_str:
                    hours_rows_html += (
                        f'<div class="yelp-hours-row"><span>{day.capitalize()}</span>'
                        f"<span>{esc(', '.join(times_str))}</span></div>"
                    )
    elif hours_text:
        cleaned = re.sub(r"^(?:⏰\s*)?Hours?:\s*", "", str(hours_text), flags=re.I).strip()
        hours_rows_html = f'<div class="yelp-fact">{esc(cleaned)}</div>'
    else:
        hours_rows_html = '<div class="yelp-muted">Hours not listed — please call to confirm.</div>'

    next_open_html = ""
    if not is_open:
        next_open = search.get_next_open_time(resource)
        if next_open:
            next_open_html = f'<div class="yelp-fact">📅 Next open: <strong>{esc(next_open)}</strong></div>'

    facts = []
    if address:
        facts.append(f'<div class="yelp-fact">📍 {esc(address)}</div>')
    if phone:
        if len(phone_digits) >= 10:
            facts.append(f'<div class="yelp-fact">📞 <a href="tel:{esc(phone_digits)}">{esc(phone)}</a></div>')
        else:
            facts.append(f'<div class="yelp-fact">📞 {esc(phone)}</div>')
    else:
        facts.append('<div class="yelp-fact yelp-muted">📞 Phone not listed</div>')
    if website:
        facts.append(
            f'<div class="yelp-fact">🔗 <a href="{esc(website)}" target="_blank" rel="noopener noreferrer">{esc(website)}</a></div>'
        )
    else:
        facts.append('<div class="yelp-fact yelp-muted">🔗 Website not listed</div>')
    if lang_str:
        facts.append(f'<div class="yelp-fact">🗣 {esc(lang_str)}</div>')
    facts.append(f'<div class="yelp-fact">✅ Last verified: <strong>{esc(verified)}</strong></div>')
    facts_html = "".join(facts)

    # Global page chrome
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
.stApp {
  background:
    radial-gradient(900px 420px at 0% -5%, #d4efe4 0%, transparent 55%),
    radial-gradient(700px 360px at 100% 0%, #e8f5ef 0%, transparent 50%),
    #F4F7F5;
}
.stApp, .stMarkdown, .stButton > button, .stLinkButton > a,
a[data-testid="stBaseLinkButton"] {
  font-family: 'DM Sans', system-ui, sans-serif !important;
}
.stButton > button, .stLinkButton > a, a[data-testid="stBaseLinkButton"] {
  border-radius: 999px !important;
  font-weight: 600 !important;
}
.stButton > button[kind="secondary"],
.stLinkButton > a,
a[data-testid="stBaseLinkButton"] {
  border: 1.5px solid #4EB086 !important;
  color: #1a2e28 !important;
  background: #fff !important;
}
.stButton > button[kind="primary"] {
  background: #4EB086 !important;
  border-color: #4EB086 !important;
}
.yelp-card, .yelp-section {
  background: #fff;
  border: 1px solid rgba(26,46,40,0.12);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  margin: 0.65rem 0 0.85rem 0;
  box-shadow: 0 1px 3px rgba(26,46,40,0.06);
  font-family: 'DM Sans', system-ui, sans-serif;
}
.yelp-name {
  margin: 0 0 0.45rem 0;
  font-size: 1.45rem;
  font-weight: 700;
  color: #1a2e28;
  line-height: 1.25;
}
.yelp-section-title {
  margin: 0 0 0.55rem 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a2e28;
}
.yelp-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.55rem; }
.yelp-chip {
  display: inline-flex; align-items: center;
  font-size: 0.72rem; font-weight: 600;
  padding: 0.15rem 0.5rem; border-radius: 4px;
  background: #eef7f2; color: #2d6b54;
  border: 1px solid rgba(78,176,134,0.25);
}
.yelp-chip.yelp-open { background: #10b981; color: #fff; border-color: #10b981; }
.yelp-fact { font-size: 0.9rem; color: #4a5f56; margin: 0.2rem 0; line-height: 1.45; }
.yelp-fact a { color: #3d9a72; font-weight: 600; text-decoration: none; }
.yelp-fact a:hover { text-decoration: underline; }
.yelp-muted { color: #8a9e95; font-style: italic; font-size: 0.88rem; }
.yelp-hours-row {
  display: flex; justify-content: space-between; gap: 1rem;
  font-size: 0.9rem; color: #4a5f56;
  padding: 0.28rem 0;
  border-bottom: 1px solid rgba(26,46,40,0.06);
}
.yelp-hours-row:last-child { border-bottom: none; }
.yelp-hours-row span:first-child { font-weight: 600; color: #1a2e28; min-width: 6.5rem; }
.yelp-cap { font-size: 0.84rem; color: #6b8178; margin: 0.35rem 0 0 0; }
</style>
""",
        unsafe_allow_html=True,
    )

    if st.button("← Back to search", key="yelp_back"):
        st.switch_page("Aidr.py")

    # Hero listing card
    st.markdown(
        f"""
<div class="yelp-card">
  <p class="yelp-name">{esc(name)} {open_chip}</p>
  <div class="yelp-chips">{chips_html}</div>
  <div class="yelp-facts">{facts_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if is_ryan_white:
        st.info(
            "**Ryan White HIV/AIDS Program (HRSA HAB)** — This site is listed as a "
            "Ryan White HIV/AIDS Program provider. Services may include HIV medical care, "
            "case management, and related supports for people living with HIV. "
            "Confirm eligibility and hours with the clinic."
        )

    # Action pills — Call / Website / Directions / Share
    n_actions = 1 + (1 if website else 0) + (1 if address else 0) + 1
    action_cols = st.columns(n_actions, gap="medium")
    i = 0
    with action_cols[i]:
        if phone and len(phone_digits) >= 10:
            st.link_button("Call", f"tel:{phone_digits}", use_container_width=True)
        else:
            st.button("Call", disabled=True, use_container_width=True, key="call_disabled")
    i += 1
    if website:
        with action_cols[i]:
            st.link_button("Website", website, use_container_width=True)
        i += 1
    if address:
        with action_cols[i]:
            map_utils.maps_action_button(
                "Directions",
                address,
                key="dirs_main",
                place_name=name,
            )
        i += 1
    with action_cols[i]:
        share_text = f"{name}\n"
        if address:
            share_text += f"Address: {address}\n"
        if phone:
            share_text += f"Phone: {phone}\n"
        if website:
            share_text += f"Website: {website}\n"
        if st.button("Share", use_container_width=True, key="share_main"):
            st.code(share_text)

    # Hours card
    st.markdown(
        f"""
<div class="yelp-section">
  <p class="yelp-section-title">Hours</p>
  {hours_rows_html}
  {next_open_html}
</div>
""",
        unsafe_allow_html=True,
    )

    # Location card + map
    st.markdown(
        f"""
<div class="yelp-section">
  <p class="yelp-section-title">Location</p>
  {"<div class='yelp-fact'>📍 " + esc(address) + "</div>" if address else "<div class='yelp-muted'>Address not listed</div>"}
</div>
""",
        unsafe_allow_html=True,
    )
    try:
        map_data = None
        if resource.get("latitude") and resource.get("longitude"):
            map_data = {"lat": resource["latitude"], "lon": resource["longitude"]}
        elif address:
            coords = map_utils.geocode_address(address)
            if coords:
                map_data = {"lat": coords[0], "lon": coords[1]}
        if map_data:
            import pandas as pd
            st.map(pd.DataFrame([map_data]))
        else:
            st.caption("Map unavailable (no coordinates found).")
    except Exception as e:
        st.caption(f"Map unavailable: {e}")

    # Suggest an edit
    st.markdown(
        """
<div class="yelp-section">
  <p class="yelp-section-title">Suggest an edit</p>
  <p class="yelp-cap">See something wrong? Updates are reviewed before they go live.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    g1, g2 = st.columns(2, gap="medium")
    with g1:
        st.link_button(
            "Suggest an edit",
            forms.community_report_url(name),
            use_container_width=True,
            type="primary",
        )
    with g2:
        st.link_button(
            "Clinic staff update",
            forms.clinic_update_url(name),
            use_container_width=True,
        )

    # ===========================
    # Discussion Section (Yelp-style reviews)
    # ===========================
    import streamlit.components.v1 as components

    with st.sidebar:
        try:
            auth.render_auth_sidebar()
        except Exception:
            st.caption("Sign-in unavailable right now.")

    st.markdown(
        """
<div id="aidr-comments" class="yelp-comments-anchor"></div>
<div class="yelp-section">
  <p class="yelp-section-title">Comments &amp; discussion</p>
  <p class="yelp-cap">Reviews from families — tips, wait times, and what to expect.</p>
</div>
<style>
.yelp-comments-anchor { scroll-margin-top: 1.25rem; height: 1px; }
</style>
""",
        unsafe_allow_html=True,
    )

    try:
        comments.render_discussion_section(
            resource_id=str(resource_id),
            resource_category=category,
            resource_name=name,
        )
    except Exception:
        st.info("Comments unavailable right now. Contact info above still works.")

    if st.session_state.pop("scroll_to_comments", False):
        components.html(
            """
<script>
(function () {
  function findTarget(doc) {
    return doc.getElementById("aidr-comments")
      || Array.from(doc.querySelectorAll(".yelp-section-title")).find(function (h) {
           return /Comments/i.test(h.textContent || "");
         });
  }
  function go() {
    try {
      var el = findTarget(window.parent.document);
      if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); return true; }
    } catch (e) {}
    return false;
  }
  if (!go()) {
    var n = 0;
    var t = setInterval(function () { if (go() || ++n > 50) clearInterval(t); }, 120);
  }
})();
</script>
""",
            height=0,
        )


# Run the page
render_detail_page()

