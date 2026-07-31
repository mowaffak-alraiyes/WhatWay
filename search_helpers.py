#!/usr/bin/env python3
"""
Search helper functions for better UX and search quality.
"""

import streamlit as st
from typing import List, Dict, Any, Tuple
import re

def get_search_suggestions(query: str, category: str, items: List[Dict]) -> List[str]:
    """Generate search suggestions based on query and available resources."""
    if not query or len(query) < 2:
        return []

    query_lower = query.lower()
    suggestions: List[str] = []

    # Mine real service labels from the dataset
    common_services = set()
    for item in items[:80]:
        for s in item.get("services") or []:
            label = str(s).replace("_", " ").strip()
            if label:
                common_services.add(label)
        for s in item.get("subcategories") or []:
            if s:
                common_services.add(str(s))

    # Query-shaped hints
    if "dent" in query_lower or "tooth" in query_lower or "teeth" in query_lower:
        suggestions.extend(["dental", "free dental"])
    if "kid" in query_lower or "child" in query_lower or "pediatr" in query_lower:
        suggestions.extend(["pediatric", "children's health"])
    if "mental" in query_lower or "therap" in query_lower or "counsel" in query_lower:
        suggestions.extend(["mental health", "counseling"])
    if "women" in query_lower or "pregnan" in query_lower or "prenatal" in query_lower:
        suggestions.extend(["women's health", "prenatal"])
    if "esl" in query_lower or "english" in query_lower:
        suggestions.extend(["ESL", "English classes"])
    if "legal" in query_lower or "immig" in query_lower or "asylum" in query_lower:
        suggestions.extend(["legal help", "immigration"])
    if "shelter" in query_lower or "hous" in query_lower or "homeless" in query_lower:
        suggestions.extend(["shelter", "emergency housing"])
    if "health" in query_lower or "clinic" in query_lower:
        suggestions.extend(["primary care", "free clinic"])

    # ZIP-ish
    if re.search(r"\d", query):
        suggestions.extend(["60629", "60640", "60625"])

    # Fill from dataset services that partially match the query
    for svc in sorted(common_services):
        if any(tok in svc.lower() for tok in query_lower.split() if len(tok) > 2):
            suggestions.append(svc)
        if len(suggestions) >= 8:
            break

    # Dedupe preserve order
    out = []
    seen = set()
    for s in suggestions:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:5]


def get_no_result_suggestions(query: str, category: str, items: List[Dict]) -> List[str]:
    """Buttons to offer when search returns nothing — dataset-aware + category defaults."""
    base = get_search_suggestions(query or "", category, items)
    related = get_related_searches(query or "", category)
    defaults = {
        "Healthcare": ["dental", "primary care", "mental health", "women's health", "free clinic"],
        "Education": ["ESL", "GED", "citizenship", "job training", "adult education"],
        "Resettlement / Legal / Shelter": ["legal help", "immigration", "shelter", "food pantry", "case management"],
    }.get(category, ["primary care", "ESL", "legal help"])

    # Top services actually present in this category
    counts: Dict[str, int] = {}
    for item in items[:120]:
        for s in item.get("subcategories") or []:
            counts[str(s)] = counts.get(str(s), 0) + 1
        for s in item.get("services") or []:
            label = str(s).replace("_", " ").title()
            counts[label] = counts.get(label, 0) + 1
    popular = [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:5]]

    merged = []
    seen = set()
    for s in base + related + popular + defaults:
        key = (s or "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(s)
    return merged[:5]

def get_quick_filters(category: str, items: List[Dict]) -> Dict[str, int]:
    """Get counts for quick filter buttons."""
    counts = {
        "Free": 0,
        "Open Now": 0,
        "Accepts Medicaid": 0,
        "Walk-in": 0,
    }
    
    # Import here to avoid circular imports
    try:
        import search
        has_search_module = True
    except:
        has_search_module = False
    
    from datetime import datetime
    
    for item in items:
        # Check for free services
        services_text = (item.get("services", "") + " " + item.get("name", "")).lower()
        if re.search(r'\b(free|no cost|no-cost|complimentary)\b', services_text):
            counts["Free"] += 1
        
        # Check for open now (try search module first, fallback to basic check)
        try:
            if has_search_module:
                if search.is_open_now(item):
                    counts["Open Now"] += 1
            else:
                # Basic check: if hours exist and contain current day
                hours = item.get("hours", "")
                if hours:
                    from datetime import datetime
                    current_day = datetime.now().strftime("%A")
                    if current_day.lower() in hours.lower():
                        counts["Open Now"] += 1
        except:
            pass
        
        # Check for Medicaid
        if re.search(r'\b(medicaid|medicare|insurance)\b', services_text):
            counts["Accepts Medicaid"] += 1
        
        # Check for walk-in
        if re.search(r'\b(walk.?in|walk in|no appointment)\b', services_text):
            counts["Walk-in"] += 1
    
    return counts

def render_quick_filters(category: str, items: List[Dict]) -> Dict[str, bool]:
    """Render quick filter buttons and return which are active."""
    st.markdown("**🔍 Quick Filters:**")
    
    counts = get_quick_filters(category, items)
    active_filters = st.session_state.get(f"quick_filters_{category}", {})
    
    cols = st.columns(4)
    filters = {}
    
    with cols[0]:
        if st.button(f"🟢 Free ({counts['Free']})", key=f"filter_free_{category}", 
                    type="primary" if active_filters.get("free") else "secondary"):
            active_filters["free"] = not active_filters.get("free", False)
            st.session_state[f"quick_filters_{category}"] = active_filters
            st.rerun()
        filters["free"] = active_filters.get("free", False)
    
    with cols[1]:
        if st.button(f"🟢 Open Now ({counts['Open Now']})", key=f"filter_open_{category}",
                    type="primary" if active_filters.get("open_now") else "secondary"):
            active_filters["open_now"] = not active_filters.get("open_now", False)
            st.session_state[f"quick_filters_{category}"] = active_filters
            st.rerun()
        filters["open_now"] = active_filters.get("open_now", False)
    
    with cols[2]:
        if st.button(f"🔵 Medicaid ({counts['Accepts Medicaid']})", key=f"filter_medicaid_{category}",
                    type="primary" if active_filters.get("medicaid") else "secondary"):
            active_filters["medicaid"] = not active_filters.get("medicaid", False)
            st.session_state[f"quick_filters_{category}"] = active_filters
            st.rerun()
        filters["medicaid"] = active_filters.get("medicaid", False)
    
    with cols[3]:
        if st.button(f"🟠 Walk-in ({counts['Walk-in']})", key=f"filter_walkin_{category}",
                    type="primary" if active_filters.get("walkin") else "secondary"):
            active_filters["walkin"] = not active_filters.get("walkin", False)
            st.session_state[f"quick_filters_{category}"] = active_filters
            st.rerun()
        filters["walkin"] = active_filters.get("walkin", False)
    
    return filters

def filter_by_quick_filters(items: List[Dict], filters: Dict[str, bool]) -> List[Dict]:
    """Filter items based on quick filter selections."""
    if not any(filters.values()):
        return items
    
    try:
        import search
        has_search_module = True
    except:
        has_search_module = False
    
    filtered = []
    for item in items:
        services_text = (item.get("services", "") + " " + item.get("name", "")).lower()
        match = True
        
        if filters.get("free"):
            if not re.search(r'\b(free|no cost|no-cost|complimentary)\b', services_text):
                match = False
        
        if filters.get("open_now"):
            try:
                if has_search_module:
                    if not search.is_open_now(item):
                        match = False
                else:
                    # Basic check: if hours exist and contain current day
                    hours = item.get("hours", "")
                    if hours:
                        from datetime import datetime
                        current_day = datetime.now().strftime("%A")
                        if current_day.lower() not in hours.lower():
                            match = False
                    else:
                        match = False
            except:
                match = False
        
        if filters.get("medicaid"):
            if not re.search(r'\b(medicaid|medicare|insurance)\b', services_text):
                match = False
        
        if filters.get("walkin"):
            if not re.search(r'\b(walk.?in|walk in|no appointment)\b', services_text):
                match = False
        
        if match:
            filtered.append(item)
    
    return filtered

def get_related_searches(query: str, category: str) -> List[str]:
    """Generate related search suggestions."""
    related = []
    query_lower = query.lower()
    
    # Healthcare related searches
    if category == "Healthcare":
        if "dental" in query_lower:
            related.extend(["pediatric dental", "free dental", "dental 60629"])
        if "pediatric" in query_lower:
            related.extend(["children's health", "pediatric care", "kids doctors"])
        if "mental" in query_lower:
            related.extend(["therapy", "counseling", "mental health services"])
    
    # Education related searches
    elif category == "Education":
        if "esl" in query_lower or "english" in query_lower:
            related.extend(["citizenship classes", "GED prep", "adult education"])
        if "citizenship" in query_lower:
            related.extend(["ESL classes", "civics", "citizenship test prep"])
    
    # Legal/Shelter related searches
    elif category == "Resettlement / Legal / Shelter":
        if "legal" in query_lower or "immigration" in query_lower:
            related.extend(["asylum help", "DACA", "immigration lawyer"])
        if "shelter" in query_lower or "housing" in query_lower:
            related.extend(["emergency housing", "homeless services", "temporary shelter"])
    
    return related[:3]  # Return top 3

def render_search_suggestions(query: str, category: str, items: List[Dict]) -> None:
    """Render search suggestions to help users."""
    suggestions = get_search_suggestions(query, category, items)
    related = get_related_searches(query, category)
    
    if suggestions or related:
        st.markdown("**💡 Suggestions:**")
        
        if suggestions:
            cols = st.columns(min(len(suggestions), 5))
            for i, suggestion in enumerate(suggestions):
                with cols[i]:
                    if st.button(f"🔍 {suggestion}", key=f"suggestion_{i}_{category}"):
                        # Trigger search with suggestion
                        st.session_state[f"search_suggestion_{category}"] = suggestion
                        st.rerun()
        
        if related:
            st.markdown("**Related searches:** " + " • ".join([f"*{r}*" for r in related]))

def get_recent_searches(category: str) -> List[str]:
    """Get recent searches for this category."""
    recent = st.session_state.get(f"recent_searches_{category}", [])
    return recent[-5:]  # Last 5 searches

def add_to_recent_searches(query: str, category: str) -> None:
    """Add query to recent searches."""
    recent = st.session_state.get(f"recent_searches_{category}", [])
    if query and query not in recent:
        recent.append(query)
        # Keep only last 10
        recent = recent[-10:]
        st.session_state[f"recent_searches_{category}"] = recent

def render_recent_searches(category: str) -> None:
    """Render recent searches in sidebar."""
    recent = get_recent_searches(category)
    if recent:
        st.markdown("**🕐 Recent Searches:**")
        for search_term in reversed(recent):  # Most recent first
            if st.button(f"🔍 {search_term}", key=f"recent_{search_term}_{category}"):
                st.session_state[f"search_suggestion_{category}"] = search_term
                st.rerun()

def render_confidence_indicator(score: float, max_score: float = 1.0) -> None:
    """Render a visual confidence indicator for search results."""
    if max_score == 0:
        return
    
    percentage = min(score / max_score, 1.0) * 100
    
    if percentage >= 80:
        color = "🟢"
        label = "Excellent match"
    elif percentage >= 60:
        color = "🟡"
        label = "Good match"
    elif percentage >= 40:
        color = "🟠"
        label = "Fair match"
    else:
        color = "⚪"
        label = "Possible match"
    
    st.caption(f"{color} {label} ({percentage:.0f}%)")

def render_share_results_button(results: List[Dict], query: str, category: str) -> None:
    """Render a button to share search results."""
    if not results:
        return
    
    share_text = f"Found {len(results)} {category.lower()} resources for '{query}':\n\n"
    for i, item in enumerate(results[:5], 1):
        share_text += f"{i}. {item.get('name', 'Unknown')}\n"
        if item.get('address'):
            share_text += f"   📍 {item['address']}\n"
        if item.get('phone'):
            share_text += f"   📞 {item['phone']}\n"
        share_text += "\n"
    
    if st.button("📤 Share Results", key=f"share_{category}_{query}"):
        st.code(share_text)
        st.info("💡 Copy the text above to share these results!")

