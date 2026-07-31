#!/usr/bin/env python3
"""
Enhanced search module with fuzzy matching and "open now" detection.
"""

import re
from datetime import datetime, time, timedelta
from typing import List, Dict, Any, Tuple, Optional
import streamlit as st
from rapidfuzz import fuzz
import pytz

# ===========================
# Search Configuration
# ===========================

# Base synonyms for keyword expansion - enhanced with subcategory mappings
BASE_SYNONYMS = {
    # Healthcare
    "health": ["health", "healthcare", "medical", "clinic", "hospital", "doctor", "physician", "health center"],
    "dental": ["dental", "dentist", "oral", "teeth", "tooth", "dental care", "exams", "cleanings", "x-rays", "extractions"],
    "pediatric": ["pediatric", "pediatrician", "child", "children", "kids", "baby", "infant", "adolescent", "youth"],
    "mental": ["mental", "therapy", "therapist", "counseling", "counselor", "psychology", "psychiatric", "psychiatry", "behavioral health", "behavioral"],
    "primary": ["primary", "family", "general", "internal", "medicine", "doctor", "physician", "primary care", "family medicine"],
    "womens": ["women", "womens", "obstetrics", "gynecology", "obgyn", "ob/gyn", "prenatal", "midwifery"],
    "urgent": ["urgent", "emergency", "walk-in", "same-day", "walk in", "24/7", "24 hours"],
    "hiv": ["hiv", "sti", "std", "sexually transmitted"],
    "nutrition": ["nutrition", "nutritional", "dietitian", "diet"],
    "mobile": ["mobile", "screening", "screenings", "glucose", "blood pressure", "immunization", "vaccination", "vaccine"],
    "specialty": ["surgery", "podiatry", "surgical", "specialty"],
    
    # Education
    "education": ["education", "school", "learning", "class", "course", "training"],
    "esl": ["esl", "english", "english language", "language", "language training", "english classes", "language learning", "english tutoring"],
    "citizenship": ["citizenship", "citizenship preparation", "citizenship classes", "citizenship exam", "civics"],
    "ged": ["ged", "high school", "diploma", "education", "adult education", "adult basic education"],
    "literacy": ["literacy", "literate", "reading", "adult literacy", "basic literacy", "family literacy"],
    "youth": ["youth", "after-school", "after school", "tutoring", "homework help", "mentoring", "youth programs"],
    "computer": ["computer", "digital literacy", "computer skills", "computer classes", "digital", "technology"],
    "workforce": ["workforce", "job training", "employment", "career", "vocational", "job readiness", "job placement", "workforce readiness"],
    "financial": ["financial literacy", "financial", "money management", "budgeting"],
    
    # Resettlement/Legal/Shelter
    "legal": ["legal", "lawyer", "attorney", "immigration", "asylum", "daca", "daca", "family reunification", "court", "advocacy", "legal services"],
    "resettlement": ["resettlement", "refugee resettlement", "case management", "welcoming center"],
    "shelter": ["shelter", "housing", "homeless", "emergency housing", "emergency shelter", "domestic violence", "temporary housing"],
    "employment": ["employment", "job", "job placement", "job readiness", "job training", "job coaching", "career", "vocational"],
    "benefits": ["benefits", "snap", "food stamps", "medicaid", "cash assistance", "public benefits", "enrollment"],
    "food": ["food", "food pantry", "pantry", "food bank", "food distribution", "free meals", "meals"],
    "crisis": ["crisis", "hotline", "24-hour", "emergency", "abuse", "neglect"],
    
    # Common
    "free": ["free", "no cost", "no-cost", "complimentary", "pro bono"],
    "low cost": ["low cost", "low-cost", "affordable", "sliding scale"],
    "medicaid": ["medicaid", "medicare", "insurance", "coverage"],
}

# ===========================
# Time and Availability Functions
# ===========================

def is_open_now(record: Dict[str, Any], timezone: str = "America/Chicago") -> bool:
    """Check if a service is currently open."""
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        current_day = now.strftime("%A").lower()
        current_time = now.time()
        
        hours = record.get("hours", {})
        if current_day not in hours:
            return False
        
        time_ranges = hours[current_day]
        for start_time, end_time in time_ranges:
            # Convert tuple to time object
            start = time(start_time[0], start_time[1])
            end = time(end_time[0], end_time[1])
            
            if start <= current_time <= end:
                return True
        
        return False
    except Exception:
        return False

def get_next_open_time(record: Dict[str, Any], timezone: str = "America/Chicago") -> Optional[str]:
    """Get the next time a service will be open."""
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        # Check next 7 days
        for i in range(7):
            check_date = now + timedelta(days=i)
            day_name = check_date.strftime("%A").lower()
            
            hours = record.get("hours", {})
            if day_name in hours:
                time_ranges = hours[day_name]
                if time_ranges:
                    start_time, _ = time_ranges[0]
                    next_open = datetime.combine(check_date.date(), time(start_time[0], start_time[1]))
                    
                    if i == 0 and next_open <= now:
                        continue  # Already passed today
                    
                    return next_open.strftime("%A %I:%M %p")
        
        return None
    except Exception:
        return None

# ===========================
# Search Functions
# ===========================

@st.cache_resource
def get_search_patterns():
    """Get compiled regex patterns for search - enhanced with subcategories."""
    return {
        "zip": re.compile(r'\b(60\d{3})\b'),
        "service": re.compile(r'\b(dental|pediatric|mental|primary|urgent|esl|ged|legal|shelter|womens|hiv|nutrition|mobile|specialty|citizenship|literacy|youth|computer|workforce|financial|resettlement|employment|benefits|food|crisis)\b', re.I),
        "day": re.compile(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b', re.I),
        "time": re.compile(r'\b(now|today|open|available)\b', re.I),
    }

def extract_key_terms(query: str) -> Dict[str, str]:
    """Extract key terms from query using synonyms and patterns."""
    query_lower = query.lower()
    patterns = get_search_patterns()
    
    extracted = {}
    
    # Extract ZIP code
    zip_match = patterns["zip"].search(query)
    if zip_match:
        extracted["zip"] = zip_match.group(1)
    
    # Extract service type
    service_match = patterns["service"].search(query)
    if service_match:
        extracted["service"] = service_match.group(1).lower()
    
    # Extract day
    day_match = patterns["day"].search(query)
    if day_match:
        day = day_match.group(1).lower()
        # Normalize day names
        day_map = {
            "mon": "monday", "tue": "tuesday", "wed": "wednesday",
            "thu": "thursday", "fri": "friday", "sat": "saturday", "sun": "sunday"
        }
        extracted["day"] = day_map.get(day, day)
    
    # Extract time preference
    time_match = patterns["time"].search(query)
    if time_match:
        extracted["time"] = time_match.group(1).lower()
    
    return extracted

def expand_query_terms(query: str) -> List[str]:
    """Expand query with synonyms for better matching."""
    query_lower = query.lower()
    expanded_terms = [query_lower]
    
    for base_term, synonyms in BASE_SYNONYMS.items():
        if base_term in query_lower:
            for synonym in synonyms:
                if synonym not in query_lower:
                    expanded_query = query_lower.replace(base_term, synonym)
                    expanded_terms.append(expanded_query)
    
    return expanded_terms

def fuzzy_score(record: Dict[str, Any], query: str) -> float:
    """Calculate fuzzy match score for a record - more flexible matching."""
    search_blob = record.get("search_blob", "")
    if not search_blob:
        return 0.0
    
    query_lower = query.lower()
    
    # Multiple fuzzy matching strategies for flexibility
    # 1. Token sort ratio (handles word order differences)
    token_sort = fuzz.token_sort_ratio(search_blob, query_lower) / 100.0
    
    # 2. Token set ratio (handles word repetition/extra words)
    token_set = fuzz.token_set_ratio(search_blob, query_lower) / 100.0
    
    # 3. Partial ratio (matches partial strings - good for abbreviations)
    partial = fuzz.partial_ratio(search_blob, query_lower) / 100.0
    
    # 4. Word-based partial matching (catches "dent" matching "dental")
    words_query = set(query_lower.split())
    words_blob = set(search_blob.split())
    word_overlap = len(words_query & words_blob) / max(len(words_query), 1)
    
    # 5. Character n-gram overlap (catches misspellings, variations)
    # Simple bigram similarity
    def get_bigrams(text):
        return set(text[i:i+2] for i in range(len(text)-1))
    query_bigrams = get_bigrams(query_lower)
    blob_bigrams = get_bigrams(search_blob)
    bigram_overlap = len(query_bigrams & blob_bigrams) / max(len(query_bigrams), 1) if query_bigrams else 0
    
    # Combine scores (weighted average favoring stronger matches)
    combined_score = (
        token_sort * 0.3 +      # Word order flexibility
        token_set * 0.25 +       # Extra word tolerance
        partial * 0.2 +          # Partial match (abbreviations)
        word_overlap * 0.15 +    # Word-level matching
        bigram_overlap * 0.1     # Character-level similarity
    )
    
    return min(combined_score, 1.0)  # Cap at 1.0

def must_have_patterns(query: str, category: str) -> List[re.Pattern]:
    """Get must-have patterns based on query and category - FLEXIBLE matching (not strict)."""
    patterns = []
    query_lower = query.lower()
    
    # Extract meaningful terms (ignore stopwords)
    stopwords = {"find", "need", "want", "looking", "for", "near", "in", "at", "the", "a", "an", "help", "me", "please"}
    meaningful_terms = [w for w in query_lower.split() if w not in stopwords and len(w) > 2]
    
    # Only require patterns if query has very specific terms (make it lenient)
    # Category-specific patterns with subcategory support - MORE FLEXIBLE
    if category == "Healthcare":
        if any(term in query_lower for term in ["dental", "dentist", "teeth", "tooth", "oral"]):
            patterns.append(re.compile(r'\b(dental|dentist|oral|teeth|tooth|dental care)\b', re.I))
        if any(term in query_lower for term in ["pediatric", "children", "kids", "child", "adolescent", "youth"]):
            patterns.append(re.compile(r'\b(pediatric|pediatrician|child|children|kids|baby|infant|adolescent)\b', re.I))
        if any(term in query_lower for term in ["mental", "therapy", "therapist", "counseling", "psychiatric", "behavioral"]):
            patterns.append(re.compile(r'\b(mental|therapy|therapist|counseling|counselor|psychology|psychiatric|behavioral)\b', re.I))
        if any(term in query_lower for term in ["women", "womens", "obgyn", "prenatal", "obstetrics", "gynecology"]):
            patterns.append(re.compile(r'\b(women\'?s health|obstetrics|gynecology|ob/gyn|prenatal|midwifery)\b', re.I))
        if any(term in query_lower for term in ["hiv", "sti", "std"]):
            patterns.append(re.compile(r'\b(hiv|sti|std|sexually transmitted)\b', re.I))
        if any(term in query_lower for term in ["primary", "family medicine", "internal medicine"]):
            patterns.append(re.compile(r'\b(primary care|family medicine|internal medicine|primary|family|general)\b', re.I))
    
    elif category == "Education":
        if any(term in query_lower for term in ["esl", "english", "language"]):
            patterns.append(re.compile(r'\b(esl|english|english language|language training|language classes)\b', re.I))
        if any(term in query_lower for term in ["citizenship", "civics"]):
            patterns.append(re.compile(r'\b(citizenship|citizenship preparation|civics)\b', re.I))
        if any(term in query_lower for term in ["ged", "high school", "diploma"]):
            patterns.append(re.compile(r'\b(ged|high.?school|diploma|adult education)\b', re.I))
        if any(term in query_lower for term in ["youth", "after-school", "tutoring", "homework"]):
            patterns.append(re.compile(r'\b(youth|after.?school|tutoring|homework help|mentoring)\b', re.I))
        if any(term in query_lower for term in ["workforce", "job training", "employment", "career"]):
            patterns.append(re.compile(r'\b(workforce|job training|employment|career|vocational|job readiness)\b', re.I))
        if any(term in query_lower for term in ["computer", "digital", "technology"]):
            patterns.append(re.compile(r'\b(computer|digital literacy|computer skills|technology)\b', re.I))
    
    elif category == "Resettlement / Legal / Shelter":
        if any(term in query_lower for term in ["legal", "lawyer", "attorney", "immigration", "asylum", "daca"]):
            patterns.append(re.compile(r'\b(legal|lawyer|attorney|immigration|asylum|daca|legal services)\b', re.I))
        if any(term in query_lower for term in ["shelter", "housing", "homeless", "emergency"]):
            patterns.append(re.compile(r'\b(shelter|housing|homeless|emergency housing|emergency shelter)\b', re.I))
        if any(term in query_lower for term in ["resettlement", "refugee", "case management"]):
            patterns.append(re.compile(r'\b(refugee resettlement|resettlement|case management)\b', re.I))
        if any(term in query_lower for term in ["benefits", "snap", "medicaid", "food stamps"]):
            patterns.append(re.compile(r'\b(benefits|snap|food stamps|medicaid|cash assistance|public benefits)\b', re.I))
        if any(term in query_lower for term in ["food", "pantry", "meals"]):
            patterns.append(re.compile(r'\b(food|food pantry|pantry|food bank|free meals)\b', re.I))
        if any(term in query_lower for term in ["employment", "job", "job placement"]):
            patterns.append(re.compile(r'\b(employment|job|job placement|job training|job coaching)\b', re.I))
    
    return patterns

def rank_items(
    items: List[Dict[str, Any]], 
    query: str, 
    category: str,
    zip_filter: str = "All",
    lang_filter: str = "All", 
    service_filter: str = "All",
    day_filter: str = "All"
) -> List[Tuple[float, Dict[str, Any]]]:
    """Enhanced ranking with fuzzy matching and filters."""
    
    if not items or not query.strip():
        return []
    
    # Extract key terms from query
    key_terms = extract_key_terms(query)
    
    # Get must-have patterns
    must_have = must_have_patterns(query, category)
    
    # Expand query terms
    expanded_queries = expand_query_terms(query)
    
    scored_items = []
    
    for item in items:
        score = 0.0
        
        # Apply filters
        if zip_filter != "All" and item.get("zip_code") != zip_filter:
            continue
        
        if lang_filter != "All":
            languages = item.get("languages", [])
            if lang_filter not in languages:
                continue
        
        if service_filter != "All":
            services = item.get("services", [])
            if service_filter not in services:
                continue
        
        if day_filter != "All":
            hours = item.get("hours", {})
            if day_filter not in hours:
                continue
        
        # Check must-have patterns - MAKE IT SOFT/WARNING, NOT HARD FILTER
        # Only skip if query is very specific and pattern definitely doesn't match
        search_text = item.get("search_blob", "")
        if must_have:
            # Instead of hard filter, just reduce score if pattern doesn't match
            # This allows conceptual matches through even if exact words don't match
            pattern_match = any(pattern.search(search_text) for pattern in must_have)
            if not pattern_match:
                # Don't skip - just reduce score (be more flexible)
                # Only skip if score would be very low anyway
                pass  # Let fuzzy matching handle it instead
        
        # Base fuzzy score
        max_fuzzy_score = 0.0
        for expanded_query in expanded_queries:
            fuzzy_score_val = fuzzy_score(item, expanded_query)
            max_fuzzy_score = max(max_fuzzy_score, fuzzy_score_val)
        
        score += max_fuzzy_score * 0.7  # 70% weight for fuzzy matching (increased from 60%)
        
        # Bonus for exact matches
        query_lower = query.lower()
        if query_lower in search_text:
            score += 0.3
        
        # Bonus for name matches
        name = item.get("name", "").lower()
        if query_lower in name:
            score += 0.2
        
        # Bonus for service matches (both normalized services and subcategories)
        services = item.get("services", [])
        subcategories = item.get("subcategories", [])
        services_text = item.get("services_text", "").lower()
        
        # Check normalized services
        for service in services:
            if service in query_lower:
                score += 0.15
        
        # Bonus for subcategory matches (higher weight as they're more specific)
        for subcat in subcategories:
            if subcat.lower() in query_lower:
                score += 0.2
        
        # Bonus for matches in full services text (semantic matching)
        if services_text:
            for synonym_list in BASE_SYNONYMS.values():
                for synonym in synonym_list:
                    if synonym in query_lower and synonym in services_text:
                        score += 0.1
                        break
        
        # Partial word matching - catch "dent" matching "dental", "psych" matching "psychology"
        # Split query into words and check if any word is a prefix/substring of service words
        query_words = query_lower.split()
        service_words = services_text.split()
        for q_word in query_words:
            if len(q_word) >= 3:  # Only check words 3+ chars (avoid "a", "an", "the")
                # Check if query word is contained in any service word (or vice versa)
                for s_word in service_words:
                    if q_word in s_word or s_word in q_word:
                        score += 0.05  # Small bonus for partial matches
                        break
        
        # Conceptual matching - if query mentions general concepts, boost scores
        # e.g., "health services" should match clinics, centers, etc.
        general_concepts = {
            "health": ["clinic", "center", "care", "medical", "health"],
            "help": ["assistance", "support", "services", "help", "aid"],
            "care": ["treatment", "care", "services", "support"],
            "class": ["education", "training", "course", "class", "learning"],
            "food": ["pantry", "meals", "food", "nutrition", "hunger"],
            "housing": ["shelter", "housing", "home", "residence"],
            "legal": ["law", "attorney", "counsel", "immigration", "legal"]
        }
        for concept, related_terms in general_concepts.items():
            if concept in query_lower:
                if any(term in search_text for term in related_terms):
                    score += 0.08  # Bonus for conceptual match
        
        # Bonus for "open now"
        if key_terms.get("time") in ["now", "today", "open"]:
            if is_open_now(item):
                score += 0.4
        
        # Bonus for ZIP match
        if key_terms.get("zip"):
            if item.get("zip_code") == key_terms["zip"]:
                score += 0.3
        
        # Bonus for day match
        if key_terms.get("day"):
            hours = item.get("hours", {})
            if key_terms["day"] in hours:
                score += 0.2
        
        scored_items.append((score, item))
    
    # Sort by score (highest first), but prioritize "open now" when user queries timing
    query_lower = query.lower()
    timing_keywords = ["now", "today", "open", "available", "immediate", "urgent"]
    wants_timing = any(kw in query_lower for kw in timing_keywords) or key_terms.get("time")
    
    # If user wants timing, sort by: open_now status first, then score
    if wants_timing:
        def sort_key(x):
            score, item = x
            is_open = is_open_now(item)
            # Open items get +1000 to sort first, then by score
            return (is_open, score)
        scored_items.sort(key=sort_key, reverse=True)
    else:
        # Normal sort by score
        scored_items.sort(key=lambda x: x[0], reverse=True)
    
    # Filter out very low scores - MORE LENIENT (lower threshold for flexibility)
    # Changed from 0.1 to 0.05 to allow more results through
    return [(score, item) for score, item in scored_items if score > 0.05]

# ===========================
# Utility Functions
# ===========================

def detect_zip_from_query(query: str) -> Optional[str]:
    """Detect ZIP code from query."""
    patterns = get_search_patterns()
    zip_match = patterns["zip"].search(query)
    return zip_match.group(1) if zip_match else None

def detect_service_from_query(query: str, category: str) -> Optional[str]:
    """Detect service type from query."""
    key_terms = extract_key_terms(query)
    return key_terms.get("service")

def detect_day_from_query(query: str) -> Optional[str]:
    """Detect day from query."""
    key_terms = extract_key_terms(query)
    return key_terms.get("day")

def clean_query_of_zip(query: str) -> str:
    """Remove ZIP code from query."""
    patterns = get_search_patterns()
    return patterns["zip"].sub("", query).strip()

def clean_query_of_service_and_day(query: str, detected_service: str = None, detected_day: str = None) -> str:
    """Remove detected service and day terms from query."""
    cleaned = query
    
    if detected_service:
        cleaned = re.sub(rf'\b{re.escape(detected_service)}\b', '', cleaned, flags=re.I)
    
    if detected_day:
        cleaned = re.sub(rf'\b{re.escape(detected_day)}\b', '', cleaned, flags=re.I)
    
    return cleaned.strip()
