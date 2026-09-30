#!/usr/bin/env python3
"""
Map utilities: Google Maps links + optional Streamlit pin map.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

CHICAGO_CENTER = (41.8781, -87.6298)


def _clean_address(address: str) -> str:
    """Normalize address for Maps / Nominatim (strip emoji, suite, ZIP+4 quirks)."""
    if not address:
        return ""
    text = str(address).strip()
    # Pin emoji / labels (display-only; must not go to geocoder)
    text = re.sub(r"^[📍📌]\s*", "", text)
    text = re.sub(r"^(?:address|location)\s*:?\s*", "", text, flags=re.I)
    text = text.replace("📍", " ").replace("📌", " ")
    # Parenthetical notes: (inside Anne M. Jeans Elementary School)
    text = re.sub(r"\([^)]*\)", " ", text)
    # Door / suite / unit / floor noise
    text = re.sub(
        r"\b(?:door|ste\.?|suite|unit|apt\.?|apartment|fl\.?|floor|rm\.?|room|bldg\.?|building)\s*#?\s*[\w-]+\b",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"#\s*\w+", " ", text)
    # ZIP+4 → ZIP5
    text = re.sub(r"\b(\d{5})-\d{4}\b", r"\1", text)
    # "IL, 60123" → "IL 60123"
    text = re.sub(r"\b([A-Z]{2})\s*,\s*(\d{5})\b", r"\1 \2", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,")
    return text


def _geocode_fallbacks(original: str, cleaned: str) -> List[str]:
    """Extra Nominatim queries for awkward suburban / school-based addresses."""
    out: List[str] = []
    raw = str(original or "")
    # School / landmark inside parentheses
    for m in re.finditer(r"\((?:inside\s+)?([^)]+)\)", raw, flags=re.I):
        place = m.group(1).strip()
        city_m = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s+(\d{5})", cleaned, re.I)
        if city_m and place:
            out.append(f"{place}, {city_m.group(1).strip()}, {city_m.group(2).upper()}")
            out.append(f"{place}, {city_m.group(1).strip()}, {city_m.group(2).upper()} {city_m.group(3)}")
    return out


def google_maps_url(address: str) -> str:
    """Open place in Google Maps (same destination deep-link as directions)."""
    return google_maps_dir_url(address)


def google_maps_dir_url(address: str) -> str:
    clean = _clean_address(address)
    return f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(clean)}"


def apple_maps_url(address: str) -> str:
    """Apple Maps directions to address (works on iOS/macOS)."""
    clean = _clean_address(address)
    return f"https://maps.apple.com/?daddr={quote_plus(clean)}"


@st.dialog("Open in Maps")
def maps_app_chooser(address: str, place_name: str = ""):
    """Ask: Apple Maps, Google Maps, or dismiss."""
    clean = _clean_address(address)
    title = place_name.strip() if place_name else "This place"
    st.markdown(f"**{title}**")
    st.caption(clean or "No address")
    st.write("Which maps app do you want to use?")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.link_button("Apple Maps", apple_maps_url(clean), use_container_width=True)
    with c2:
        st.link_button("Google Maps", google_maps_dir_url(clean), use_container_width=True)
    with c3:
        if st.button("Dismiss", use_container_width=True, type="secondary"):
            st.rerun()


def _clear_sticky_map_flags() -> None:
    """Remove leftover open flags that re-opened the dialog on every rerun."""
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("_maps_open_"):
            del st.session_state[k]


def maps_action_button(
    label: str,
    address: str,
    *,
    key: str,
    place_name: str = "",
    use_container_width: bool = True,
) -> None:
    """Map / Get Directions: same chooser (Apple, Google, or dismiss).

    Opens the dialog only on the Map button press (one-shot). A sticky
    session flag used to reopen "Open in Maps" whenever any sidebar
    toggle/dropdown caused a rerun.
    """
    clean = _clean_address(address)
    if not clean:
        return

    # One-time cleanup of the old sticky-flag pattern
    if not st.session_state.get("_maps_flags_cleared"):
        _clear_sticky_map_flags()
        st.session_state["_maps_flags_cleared"] = True

    trigger = "_maps_dialog_trigger"

    def _open_maps():
        st.session_state[trigger] = {
            "address": clean,
            "place_name": place_name,
            "button_key": key,
        }

    st.button(label, key=key, use_container_width=use_container_width, on_click=_open_maps)

    # Pop so this runs once for the clicked Map button only
    pending = st.session_state.get(trigger)
    if pending and pending.get("button_key") == key:
        st.session_state.pop(trigger, None)
        maps_app_chooser(
            pending.get("address") or clean,
            place_name=pending.get("place_name") or place_name,
        )


# Bump when address cleaning changes so stale "None" cache entries expire
_GEOCODE_CACHE_VER = 3


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_address(address: str, _ver: int = _GEOCODE_CACHE_VER) -> Optional[Tuple[float, float]]:
    """Geocode via Nominatim. Returns (lat, lon) or None."""
    original = str(address or "")
    clean = _clean_address(original)
    if not clean:
        return None

    candidates = [clean]
    if "USA" not in clean.upper() and "United States" not in clean:
        candidates.append(f"{clean}, USA")
    m = re.search(
        r"^(.+?),\s*([^,]+),\s*([A-Z]{2})\s+(\d{5})\b",
        clean,
        re.I,
    )
    if m:
        street, city, state, zip5 = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).upper(),
            m.group(4),
        )
        candidates.append(f"{street}, {city}, {state} {zip5}, USA")
        candidates.append(f"{street}, {city}, {state}, USA")
    candidates.extend(_geocode_fallbacks(original, clean))

    seen = set()
    for query in candidates:
        q = query.strip()
        if not q or q in seen:
            continue
        seen.add(q)
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "us"},
                headers={"User-Agent": "WhatWayRefugeeResources/1.0 (demo; contact@localhost)"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
            time.sleep(0.2)
        except Exception as e:
            print(f"Geocoding error for '{q}': {e}")
    return None


def batch_geocode_addresses(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for item in items:
        if item.get("latitude") and item.get("longitude"):
            continue
        address = item.get("address", "")
        coords = geocode_address(address) if address else None
        if coords:
            item["latitude"], item["longitude"] = coords
    return items


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3959.0
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat, dlon = lat2_rad - lat1_rad, lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def sort_by_distance(
    items: List[Dict[str, Any]],
    user_location: Optional[Tuple[float, float]] = None,
) -> List[Dict[str, Any]]:
    if not items:
        return items
    user_lat, user_lon = user_location or CHICAGO_CENTER
    for item in items:
        lat, lon = item.get("latitude"), item.get("longitude")
        if lat and lon:
            item["distance_miles"] = calculate_distance(user_lat, user_lon, lat, lon)
        else:
            item["distance_miles"] = float("inf")
    return sorted(items, key=lambda x: x.get("distance_miles", float("inf")))


def render_map_view(
    items: List[Dict[str, Any]],
    category: str = "",
    user_location: Optional[Tuple[float, float]] = None,
    sort_by_dist: bool = False,
) -> None:
    """Show an embedded Google Map + per-place Maps links (always works)."""
    if not items:
        st.caption("No places to map.")
        return

    cleaned = []
    for item in items:
        addr = _clean_address(item.get("address") or "")
        if addr:
            cleaned.append({**item, "address": addr})

    if not cleaned:
        st.caption("These listings don’t have street addresses for a map.")
        return

    # Always-working embed for the first result (and nearby area)
    primary = cleaned[0]["address"]
    embed = (
        "https://maps.google.com/maps"
        f"?q={quote_plus(primary)}&z=12&output=embed"
    )
    components.html(
        f"""
        <iframe
          title="Map"
          width="100%"
          height="320"
          style="border:0;border-radius:12px;"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          src="{embed}">
        </iframe>
        """,
        height=330,
    )

    # Optional pin map if geocoding succeeds quickly
    with st.spinner("Pinning locations…"):
        items_with_coords = batch_geocode_addresses([dict(i) for i in cleaned])
    if sort_by_dist:
        items_with_coords = sort_by_distance(items_with_coords, user_location)

    pin_rows = [
        {"lat": i["latitude"], "lon": i["longitude"], "name": i.get("name", "")}
        for i in items_with_coords
        if i.get("latitude") and i.get("longitude")
    ]
    if len(pin_rows) >= 1:
        st.map(pd.DataFrame(pin_rows), latitude="lat", longitude="lon", zoom=11, size=40)

    st.markdown("**Open directions**")
    for i, item in enumerate(items_with_coords, 1):
        name = item.get("name") or f"Place {i}"
        addr = item.get("address") or ""
        cols = st.columns([3, 1])
        with cols[0]:
            dist = item.get("distance_miles")
            extra = f" · {dist:.1f} mi" if isinstance(dist, (int, float)) and dist != float("inf") else ""
            st.markdown(f"**{i}. {name}**{extra}  \n{addr}")
        with cols[1]:
            maps_action_button(
                "Directions",
                addr,
                key=f"maplist_{category}_{i}_{item.get('id', i)}",
                place_name=name,
            )
