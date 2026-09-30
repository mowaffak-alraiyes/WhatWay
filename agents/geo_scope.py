"""
Multi-state resource paths + hub-city distance filters.

Listings live in refugee-resources under resources/{STATE}/…
Default active app state: RESOURCES_STATE=IL (Chicago-first UI).
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# (name, lat, lon), approximate city centers for 250-mile catchments
HUBS: Dict[str, List[Tuple[str, float, float]]] = {
    "IL": [("Chicago", 41.8781, -87.6298)],
    "IN": [("Indianapolis", 39.7684, -86.1581)],
    "CO": [("Denver", 39.7392, -104.9903)],
    "CA": [
        ("San Francisco", 37.7749, -122.4194),
        ("Los Angeles", 34.0522, -118.2437),
        ("Sacramento", 38.5816, -121.4944),
    ],
}

# Broader search seeds for Find-a-Health-Center API (hubs + surrounding cities).
# Overlaps are expected: callers dedupe by HRSA site Id / name+ZIP.
SEARCH_CITIES: Dict[str, List[Tuple[str, float, float]]] = {
    "IL": [
        ("Chicago", 41.8781, -87.6298),
        ("Aurora", 41.7606, -88.3201),
        ("Joliet", 41.5250, -88.0817),
        ("Naperville", 41.7508, -88.1535),
        ("Rockford", 42.2711, -89.0940),
        ("Peoria", 40.6936, -89.5890),
        ("Springfield", 39.7817, -89.6501),
    ],
    "IN": [
        ("Indianapolis", 39.7684, -86.1581),
        ("Fort Wayne", 41.0793, -85.1394),
        ("Evansville", 37.9716, -87.5711),
        ("South Bend", 41.6764, -86.2520),
        ("Bloomington", 39.1653, -86.5264),
        ("Lafayette", 40.4167, -86.8753),
        ("Gary", 41.5934, -87.3464),
        ("Terre Haute", 39.4667, -87.4139),
    ],
    "CO": [
        ("Denver", 39.7392, -104.9903),
        ("Aurora", 39.7294, -104.8319),
        ("Boulder", 40.0150, -105.2705),
        ("Colorado Springs", 38.8339, -104.8214),
        ("Fort Collins", 40.5853, -105.0844),
        ("Pueblo", 38.2544, -104.6091),
    ],
    "CA": [
        ("San Francisco", 37.7749, -122.4194),
        ("Oakland", 37.8044, -122.2712),
        ("San Jose", 37.3382, -121.8863),
        ("Sacramento", 38.5816, -121.4944),
        ("Los Angeles", 34.0522, -118.2437),
        ("Long Beach", 33.7701, -118.1937),
        ("San Diego", 32.7157, -117.1611),
        ("Fresno", 36.7378, -119.7871),
        ("Bakersfield", 35.3733, -119.0187),
    ],
}

DEFAULT_HUB_RADIUS_MILES = 250.0

# Any US ZIP (5-digit); previously Chicago-only 60xxx
US_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
STATE_IN_ADDRESS = re.compile(
    r",\s*([A-Z]{2})\s+\d{5}"  # ", IL 60601"
    r"|,\s*([A-Z]{2})\s*$"  # ", IL"
    r"|\b([A-Z]{2})\s+(\d{5})\b",  # "IL 60601"
    re.I,
)

CATEGORY_BASENAMES = {
    "healthcare": "healthcare.txt",
    "education": "education.txt",
    "resettlement": "ResettlementLegalShelterBasicNeeds.txt",
}


def resources_state(default: str = "IL") -> str:
    return (os.environ.get("RESOURCES_STATE") or default).strip().upper() or default


def category_rel(category: str, state: Optional[str] = None) -> str:
    """GitHub-relative path: resources/{ST}/healthcare.txt"""
    st = (state or resources_state()).upper()
    cat = (category or "healthcare").lower()
    if "educ" in cat:
        key = "education"
    elif "legal" in cat or "shelter" in cat or "resettle" in cat:
        key = "resettlement"
    else:
        key = "healthcare"
    return f"resources/{st}/{CATEGORY_BASENAMES[key]}"


def category_files_for_state(state: Optional[str] = None) -> Dict[str, str]:
    st = (state or resources_state()).upper()
    return {k: f"resources/{st}/{v}" for k, v in CATEGORY_BASENAMES.items()}


def raw_github_url(rel: str, repo: Optional[str] = None) -> str:
    repo = repo or os.environ.get("RESOURCES_GITHUB_REPO", "mowaffak-alraiyes/refugee-resources")
    return f"https://raw.githubusercontent.com/{repo}/main/{rel}"


def data_sources(state: Optional[str] = None) -> Dict[str, List[str]]:
    """Streamlit / data_loader DATA_SOURCES for the active state."""
    st = (state or resources_state()).upper()
    files = category_files_for_state(st)
    return {
        "Healthcare": [raw_github_url(files["healthcare"]), files["healthcare"]],
        "Education": [raw_github_url(files["education"]), files["education"]],
        "Resettlement / Legal / Shelter": [
            raw_github_url(files["resettlement"]),
            files["resettlement"],
        ],
    }


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613  # Earth radius miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def hubs_for(state: str) -> List[Tuple[str, float, float]]:
    return list(HUBS.get((state or "").upper(), []))


def search_cities_for(state: str) -> List[Tuple[str, float, float]]:
    """Cities to query on Find a Health Center (hubs + surrounding)."""
    st = (state or "").upper()
    cities = SEARCH_CITIES.get(st)
    if cities:
        return list(cities)
    return hubs_for(st)


def within_miles(
    lat: float,
    lon: float,
    state: str,
    radius_miles: float = DEFAULT_HUB_RADIUS_MILES,
) -> bool:
    """True if (lat,lon) is within radius of any hub for state. No hubs → True (state filter only)."""
    hubs = hubs_for(state)
    if not hubs:
        return True
    for _name, hlat, hlon in hubs:
        if haversine_miles(lat, lon, hlat, hlon) <= radius_miles:
            return True
    return False


def nearest_hub_miles(lat: float, lon: float, state: str) -> Optional[float]:
    hubs = hubs_for(state)
    if not hubs:
        return None
    return min(haversine_miles(lat, lon, hlat, hlon) for _n, hlat, hlon in hubs)


def infer_state(
    address: str = "",
    *,
    zip_code: str = "",
    explicit: str = "",
    hrsa_state: str = "",
    default: Optional[str] = None,
) -> str:
    """Best-effort USPS state from HRSA column, address, or active RESOURCES_STATE."""
    for cand in (explicit, hrsa_state):
        c = (cand or "").strip().upper()
        if len(c) == 2 and c.isalpha():
            return c
    text = f"{address or ''} {zip_code or ''}"
    m = STATE_IN_ADDRESS.search(text)
    if m:
        for g in m.groups():
            if g and len(g) == 2 and g.isalpha():
                return g.upper()
    # ZIP prefix heuristics for phase-1 states (fallback only)
    z = US_ZIP.search(text)
    if z:
        prefix = z.group(1)[:3]
        if prefix.startswith("60") or prefix.startswith("61") or prefix.startswith("62"):
            return "IL"
        if prefix.startswith("46") or prefix.startswith("47"):
            return "IN"
        if prefix.startswith("80") or prefix.startswith("81"):
            return "CO"
        if prefix.startswith("90") or prefix.startswith("91") or prefix.startswith("92") or prefix.startswith("93") or prefix.startswith("94") or prefix.startswith("95"):
            return "CA"
    return (default or resources_state()).upper()


def state_of(item: Dict[str, Any], default: Optional[str] = None) -> str:
    """Read state from an op / listing dict."""
    return infer_state(
        item.get("address") or "",
        zip_code=str(item.get("zip") or item.get("zip_code") or ""),
        explicit=str(item.get("state") or ""),
        default=default,
    )


def group_by_state(items: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        st = state_of(it)
        out.setdefault(st, []).append(it)
    return out


def parse_lat_lon(row: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Pull lat/lon from HRSA-like row keys if present."""
    for lat_k, lon_k in (
        ("Latitude", "Longitude"),
        ("latitude", "longitude"),
        ("lat", "lon"),
        ("lat", "lng"),
    ):
        try:
            lat = float(str(row.get(lat_k) or "").strip())
            lon = float(str(row.get(lon_k) or "").strip())
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except (TypeError, ValueError):
            continue
    return None


def filter_rows_by_hubs(
    rows: Iterable[Dict[str, Any]],
    *,
    radius_miles: float = DEFAULT_HUB_RADIUS_MILES,
    require_coords: bool = False,
) -> List[Dict[str, Any]]:
    """Keep rows in-state (already filtered) within hub radius when coords exist.

    Rows without coordinates: kept unless require_coords=True (state match alone).
    """
    kept: List[Dict[str, Any]] = []
    for row in rows:
        st = (row.get("state") or "").upper()
        coords = parse_lat_lon(row)
        if coords is None:
            if require_coords:
                continue
            kept.append(row)
            continue
        lat, lon = coords
        if within_miles(lat, lon, st, radius_miles):
            row = dict(row)
            row["hub_miles"] = nearest_hub_miles(lat, lon, st)
            kept.append(row)
    return kept
