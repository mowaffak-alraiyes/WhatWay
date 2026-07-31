#!/usr/bin/env python3
"""
Chicago neighborhood to ZIP code mapping.
Allows users to search by neighborhood name instead of just ZIP codes.
"""

import re
from typing import List, Tuple

NEIGHBORHOOD_TO_ZIPS = {
    # North Side
    "rogers park": ["60626", "60645"],
    "uptown": ["60613", "60640", "60657"],
    "lincoln square": ["60625", "60640"],
    "lakeview": ["60613", "60614", "60657"],
    "lincoln park": ["60614", "60657"],
    "old town": ["60610", "60614"],
    "gold coast": ["60610", "60611"],
    "river north": ["60610", "60611", "60654"],
    "loop": ["60601", "60602", "60603", "60604"],
    "south loop": ["60605", "60616"],
    
    # West Side
    "humboldt park": ["60622", "60647"],
    "west town": ["60622", "60647"],
    "wicker park": ["60622"],
    "bucktown": ["60622"],
    "ukrainian village": ["60622"],
    "logan square": ["60647"],
    "avondale": ["60618", "60641"],
    "irving park": ["60618", "60641"],
    "portage park": ["60630", "60634", "60641"],
    "austin": ["60644", "60651"],
    "garfield park": ["60624", "60644"],
    "lawndale": ["60623", "60624"],
    "little village": ["60623", "60608"],
    "pilsen": ["60608", "60616"],
    
    # South Side
    "bridgeport": ["60608", "60616"],
    "chinatown": ["60616"],
    "bronzeville": ["60615", "60653"],
    "hyde park": ["60615", "60637"],
    "kenwood": ["60615", "60637"],
    "woodlawn": ["60615", "60637"],
    "englewood": ["60621", "60636"],
    "auburn gresham": ["60620", "60628"],
    "chatham": ["60619", "60620"],
    "south shore": ["60649"],
    "calumet heights": ["60617", "60619"],
    "pullman": ["60628"],
    "roseland": ["60628"],
    "west pullman": ["60628", "60643"],
    "morgan park": ["60643"],
    "beverly": ["60643"],
    "ashburn": ["60652"],
    "archer heights": ["60632", "60638"],
    "brighton park": ["60632", "60629"],
    "mckinley park": ["60609", "60632"],
    "back of the yards": ["60609", "60632"],
    "new city": ["60609", "60632"],
    "gage park": ["60629", "60632"],
    "west lawn": ["60629"],
    "garfield ridge": ["60638"],
    "clearing": ["60638"],
    "west elsd": ["60638"],
    
    # Common variations
    "rogers park": ["60626", "60645"],
    "lincoln square": ["60625", "60640"],
    "wicker park": ["60622"],
    "logan square": ["60647"],
    "little village": ["60623", "60608"],
    "hyde park": ["60615", "60637"],
}

def get_zips_for_neighborhood(neighborhood: str) -> List[str]:
    """Get ZIP codes for a neighborhood name (case-insensitive)."""
    neighborhood_lower = neighborhood.lower().strip()
    
    # Direct match
    if neighborhood_lower in NEIGHBORHOOD_TO_ZIPS:
        return NEIGHBORHOOD_TO_ZIPS[neighborhood_lower]
    
    # Fuzzy match - check if neighborhood name contains any key
    for key, zips in NEIGHBORHOOD_TO_ZIPS.items():
        if key in neighborhood_lower or neighborhood_lower in key:
            return zips
    
    return []

def expand_neighborhood_query(query: str) -> Tuple[str, List[str]]:
    """
    Expand query to include ZIP codes if neighborhood is mentioned.
    Returns (cleaned_query, list_of_zips)
    """
    query_lower = query.lower()
    found_zips = []
    cleaned_query = query
    
    # Check each neighborhood
    for neighborhood, zips in NEIGHBORHOOD_TO_ZIPS.items():
        if neighborhood in query_lower:
            found_zips.extend(zips)
            # Remove neighborhood name from query (optional - can keep both)
            # cleaned_query = cleaned_query.replace(neighborhood, "").strip()
    
    # Remove duplicates
    found_zips = list(set(found_zips))
    
    return cleaned_query, found_zips

def get_all_neighborhoods() -> List[str]:
    """Get list of all available neighborhood names."""
    return sorted(list(NEIGHBORHOOD_TO_ZIPS.keys()))


def _zip_adjacency() -> dict:
    """ZIP → other ZIPs that share at least one neighborhood (local cluster)."""
    adj: dict = {}
    for zips in NEIGHBORHOOD_TO_ZIPS.values():
        uniq = sorted(set(str(z) for z in zips))
        for z in uniq:
            adj.setdefault(z, set())
            for other in uniq:
                if other != z:
                    adj[z].add(other)
    return adj


_ZIP_ADJ = None


def zip_neighbors(zip_code: str) -> List[str]:
    """Neighborhood-cluster neighbors for a ZIP (same area of Chicago)."""
    global _ZIP_ADJ
    if _ZIP_ADJ is None:
        _ZIP_ADJ = _zip_adjacency()
    z = str(zip_code or "").strip()
    return sorted(_ZIP_ADJ.get(z, set()))


def resolve_zip_against_known(raw: str, known_zips: List[str]) -> Tuple[str, float]:
    """
    Map a typed ZIP (possibly mistyped) to the closest known ZIP in the dataset.
    Uses digit-string similarity — no assumed typo list.
    Returns (best_zip, score_0_to_100). Empty raw → ("", 0).
    """
    from rapidfuzz import fuzz

    digits = re.sub(r"\D", "", str(raw or ""))
    if not digits or not known_zips:
        return "", 0.0

    known = sorted({str(z).strip() for z in known_zips if str(z).strip()})
    if digits in known:
        return digits, 100.0

    best_z, best_s = "", -1.0
    for z in known:
        s = float(fuzz.ratio(digits, z))
        if abs(len(digits) - len(z)) <= 1:
            s = max(s, float(fuzz.partial_ratio(digits, z)) * 0.98)
        # Prefer same area prefix without hardcoding specific typos
        if len(digits) >= 3 and len(z) >= 3 and digits[:3] == z[:3]:
            s += 10.0
        if len(digits) >= 4 and len(z) >= 4 and digits[:4] == z[:4]:
            s += 8.0
        # Different leading digit → likely different metro; demote
        if len(digits) == 5 and len(z) == 5 and digits[0] != z[0]:
            s -= 20.0
        if s > best_s:
            best_s, best_z = s, z

    if best_s < 82:
        return "", best_s
    return best_z, min(best_s, 100.0)


def nearby_zip_cluster(zip_code: str, known_zips: List[str], *, max_numeric_gap: int = 5) -> List[str]:
    """
    Nearby ZIPs for ranking:
    1) Neighborhood siblings (primary — real local cluster)
    2) Only if that set is thin, pad with numerically close same-prefix ZIPs in the dataset
    """
    z = str(zip_code or "").strip()
    if not z:
        return []
    known = {str(k).strip() for k in known_zips if str(k).strip()}
    cluster = set(zip_neighbors(z)) & known

    # Only if this ZIP isn't in any neighborhood map, pad with close same-prefix ZIPs
    if not cluster:
        try:
            z_int = int(z)
            for k in known:
                try:
                    gap = abs(int(k) - z_int)
                    if 0 < gap <= max_numeric_gap and k != z:
                        if len(k) >= 3 and len(z) >= 3 and k[:3] == z[:3]:
                            cluster.add(k)
                except ValueError:
                    continue
        except ValueError:
            pass

    return sorted(cluster)


def zip_match_tier(item_zip: str, target_zip: str, nearby: List[str]) -> str:
    """exact | nearby | none"""
    iz = str(item_zip or "").strip()
    tz = str(target_zip or "").strip()
    if not tz:
        return "none"
    if iz and iz == tz:
        return "exact"
    if iz and iz in set(nearby or []):
        return "nearby"
    return "none"

