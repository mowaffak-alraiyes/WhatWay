#!/usr/bin/env python3
"""
Data loading and caching module for community resources.
Handles parsing, normalization, and caching of resource data.
"""

import json
import re
import functools
from pathlib import Path
from typing import List, Dict, Any, Optional
import streamlit as st

# ===========================
# Constants
# ===========================

# Data sources configuration (per-state paths via RESOURCES_STATE, default IL)
try:
    from agents.geo_scope import data_sources as _geo_data_sources, US_ZIP as ZIP_PATTERN

    DATA_SOURCES = _geo_data_sources()
except Exception:
    DATA_SOURCES = {
        "Healthcare": [
            "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/IL/healthcare.txt",
            "resources/IL/healthcare.txt",
        ],
        "Education": [
            "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/IL/education.txt",
            "resources/IL/education.txt",
        ],
        "Resettlement / Legal / Shelter": [
            "https://raw.githubusercontent.com/mowaffak-alraiyes/refugee-resources/main/resources/IL/ResettlementLegalShelterBasicNeeds.txt",
            "resources/IL/ResettlementLegalShelterBasicNeeds.txt",
        ],
    }
    ZIP_PATTERN = re.compile(r"\b(\d{5})(?:-\d{4})?\b")

# Compile regex patterns once for performance
PHONE_PATTERN = re.compile(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
WEBSITE_PATTERN = re.compile(r'https?://[^\s<>"\']+')

# Service patterns for normalization with comprehensive subcategories
SERVICE_PATTERNS = {
    # Healthcare subcategories
    "dental": re.compile(r'\b(dental|dentist|oral|teeth|tooth|dental care|exams|cleanings|x.?rays|extractions)\b', re.I),
    "pediatric": re.compile(r'\b(pediatric|pediatrician|child|children|kids|baby|infant|adolescent|adolescent medicine|youth.?focused)\b', re.I),
    "mental_health": re.compile(r'\b(mental|therapy|therapist|counseling|counselor|psychology|psychiatric|psychiatry|behavioral health|behavioral)\b', re.I),
    # Avoid bare family/adult/general/internal: they false-positive ESL, legal, etc.
    "primary_care": re.compile(
        r'\b(primary care|family medicine|general medicine|internal medicine|primary medical|physician|doctor)\b',
        re.I,
    ),
    "womens_health": re.compile(r'\b(women\'?s health|obstetrics|gynecology|ob/gyn|ob-gyn|ob gyn|prenatal|midwifery|prenatal/ob)\b', re.I),
    "urgent_care": re.compile(r'\b(urgent|emergency|walk.?in|same.?day|24/7|24 hours)\b', re.I),
    "hiv_sti": re.compile(r'\b(hiv|sti|std|sexually transmitted|hiv/st?i)\b', re.I),
    "nutrition": re.compile(r'\b(nutrition|nutritional|dietitian|diet)\b', re.I),
    "mobile_screening": re.compile(r'\b(mobile|screening|screenings|glucose|blood pressure|immunization|vaccination|vaccine)\b', re.I),
    "specialty": re.compile(r'\b(surgery|podiatry|surgical|specialty)\b', re.I),
    
    # Education subcategories
    "esl": re.compile(r'\b(esl|english|english language|language training|language classes|english classes|language learning)\b', re.I),
    "citizenship": re.compile(r'\b(citizenship|citizenship preparation|citizenship classes|citizenship exam|citizenship instruction|civics)\b', re.I),
    "ged": re.compile(r'\b(ged|high.?school|diploma|adult education|adult basic education)\b', re.I),
    "literacy": re.compile(r'\b(literacy|literate|reading|adult literacy|basic literacy|family literacy)\b', re.I),
    "youth_tutoring": re.compile(r'\b(youth|after.?school|tutoring|homework help|after.?school tutoring|mentoring|youth programs)\b', re.I),
    "computer_literacy": re.compile(r'\b(computer|digital literacy|computer skills|computer classes|digital|technology)\b', re.I),
    "workforce": re.compile(r'\b(workforce|job training|employment|career|vocational|job readiness|job placement|workforce readiness|workforce development)\b', re.I),
    "financial_literacy": re.compile(r'\b(financial literacy|financial|money management|budgeting)\b', re.I),
    
    # Resettlement/Legal/Shelter subcategories
    "legal": re.compile(r'\b(legal|lawyer|attorney|immigration|asylum|daca|d?a?c?a|family reunification|court|advocacy|legal services|legal assistance)\b', re.I),
    "refugee_resettlement": re.compile(r'\b(refugee resettlement|resettlement|case management|welcoming center)\b', re.I),
    "shelter": re.compile(r'\b(shelter|housing|homeless|emergency housing|emergency shelter|domestic violence shelter|temporary housing)\b', re.I),
    "employment_assistance": re.compile(r'\b(employment|job|job placement|job readiness|job training|job coaching|career|vocational)\b', re.I),
    "benefits": re.compile(r'\b(benefits|snap|food stamps|medicaid|cash assistance|public benefits|enrollment|insurance enrollment)\b', re.I),
    "food": re.compile(r'\b(food|food pantry|pantry|food bank|food distribution|free meals|meals)\b', re.I),
    "crisis": re.compile(r'\b(crisis|hotline|24.?hour|emergency|abuse|neglect)\b', re.I),
}

# Language patterns for normalization
LANGUAGE_PATTERNS = {
    "english": re.compile(r'\b(english|inglés|anglais)\b', re.I),
    "spanish": re.compile(r'\b(spanish|español|española)\b', re.I),
    "arabic": re.compile(r'\b(arabic|عربي|arab)\b', re.I),
    "french": re.compile(r'\b(french|français|française)\b', re.I),
    "polish": re.compile(r'\b(polish|polski)\b', re.I),
    "mandarin": re.compile(r'\b(mandarin|chinese|中文|普通话)\b', re.I),
    "urdu": re.compile(r'\b(urdu|اردو)\b', re.I),
    "hindi": re.compile(r'\b(hindi|हिन्दी)\b', re.I),
}

# Day patterns for hours parsing
DAY_PATTERNS = {
    "monday": re.compile(r'\b(mon|monday)\b', re.I),
    "tuesday": re.compile(r'\b(tue|tues|tuesday)\b', re.I),
    "wednesday": re.compile(r'\b(wed|wednesday)\b', re.I),
    "thursday": re.compile(r'\b(thu|thur|thursday)\b', re.I),
    "friday": re.compile(r'\b(fri|friday)\b', re.I),
    "saturday": re.compile(r'\b(sat|saturday)\b', re.I),
    "sunday": re.compile(r'\b(sun|sunday)\b', re.I),
}

# ===========================
# Utility Functions
# ===========================

def fetch_text_from_sources(sources: List[str]) -> Optional[str]:
    """Try each source in order and return the first non-empty text."""
    import base64
    import os
    import requests
    
    for source in sources:
        try:
            if source.startswith('http'):
                # Prefer GitHub Contents API for raw.githubusercontent.com (CDN can lag)
                if "raw.githubusercontent.com/" in source:
                    parts = source.split("raw.githubusercontent.com/", 1)[1].split("/")
                    # owner/repo/ref/path...
                    if len(parts) >= 4:
                        owner, repo, ref = parts[0], parts[1], parts[2]
                        rel = "/".join(parts[3:])
                        api = f"https://api.github.com/repos/{owner}/{repo}/contents/{rel}?ref={ref}"
                        headers = {"Accept": "application/vnd.github.raw"}
                        tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
                        if tok:
                            headers["Authorization"] = f"token {tok}"
                        ar = requests.get(api, timeout=30, headers=headers)
                        if ar.status_code == 200 and ar.text.strip():
                            # raw accept returns plain text
                            if not ar.text.lstrip().startswith("{"):
                                return ar.text.strip()
                        # fallback: JSON+base64 content
                        headers_json = {"Accept": "application/vnd.github+json"}
                        if tok:
                            headers_json["Authorization"] = f"token {tok}"
                        ar = requests.get(api, timeout=30, headers=headers_json)
                        if ar.status_code == 200:
                            payload = ar.json()
                            if isinstance(payload, dict) and payload.get("content"):
                                text = base64.b64decode(payload["content"]).decode("utf-8").strip()
                                if text:
                                    return text
                response = requests.get(
                    source,
                    timeout=20,
                    headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
                )
                if response.status_code == 200:
                    text = response.text.strip()
                    if text:
                        return text
            else:
                # Local file
                path = Path(source)
                if path.exists():
                    text = path.read_text(encoding='utf-8').strip()
                    if text:
                        return text
        except Exception as e:
            print(f"Failed to fetch from {source}: {e}")
            continue
    return None

def normalize_phone(phone_text: str) -> Dict[str, str]:
    """Extract and normalize phone number."""
    if not phone_text:
        return {"phone": "", "phone_digits": ""}

    # Strip leading emoji / label (📞 or Phone:) so UI can add its own icon
    cleaned = re.sub(r"^(?:📞|phone)\s*:?\s*", "", str(phone_text), flags=re.I).strip()

    phone_match = PHONE_PATTERN.search(cleaned)
    if phone_match:
        phone = phone_match.group(1)
        phone_digits = re.sub(r"\D", "", phone)
        if len(phone_digits) == 11 and phone_digits.startswith("1"):
            phone_digits = phone_digits[1:]
        # Prefer readable (630) 474-4724 when we have 10 digits
        if len(phone_digits) == 10:
            phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
        return {"phone": phone, "phone_digits": phone_digits}

    return {"phone": cleaned, "phone_digits": re.sub(r"\D", "", cleaned)}

def normalize_website(website_text: str) -> str:
    """Extract and normalize website URL."""
    if not website_text:
        return ""
    
    # Find website URL
    website_match = WEBSITE_PATTERN.search(website_text)
    if website_match:
        return website_match.group(0)
    
    return website_text.strip()

def normalize_zip(address_text: str) -> str:
    """Extract ZIP code from address."""
    if not address_text:
        return ""
    
    zip_match = ZIP_PATTERN.search(address_text)
    if zip_match:
        return zip_match.group(1)
    
    return ""


def normalize_address(address_text: str) -> str:
    """Strip map-pin emoji / labels so Maps gets a plain street address."""
    if not address_text:
        return ""
    text = str(address_text).strip()
    text = re.sub(r"^(?:📍|address|location)\s*:?\s*", "", text, flags=re.I)
    text = re.sub(r"^📍\s*", "", text).strip()
    return text


def normalize_services(services_text: str) -> List[str]:
    """Normalize and categorize services with subcategories."""
    if not services_text:
        return []
    
    services = []
    services_lower = services_text.lower()
    
    # Check all patterns and collect matching subcategories
    for service_type, pattern in SERVICE_PATTERNS.items():
        if pattern.search(services_lower):
            services.append(service_type)
    
    return list(set(services))  # Remove duplicates

def get_availability_badges(services_text: str, name: str = "", address: str = "") -> List[str]:
    """Extract availability badges (Free, Medicaid, Walk-in, etc.) from resource description."""
    badges = []
    if not services_text:
        return badges
    
    text_lower = (services_text + " " + name + " " + address).lower()
    
    # Free services
    if re.search(r'\b(free|no cost|no-cost|complimentary|pro bono|tuition-free)\b', text_lower, re.I):
        badges.append("Free")
    
    # Low cost / Affordable
    if re.search(r'\b(low cost|low-cost|affordable|sliding scale|income-based)\b', text_lower, re.I):
        badges.append("Low Cost")
    
    # Medicaid acceptance
    if re.search(r'\b(medicaid|medicare|insurance|accepts medicaid|medicaid accepted)\b', text_lower, re.I):
        badges.append("Accepts Medicaid")
    
    # Walk-in / No appointment
    if re.search(r'\b(walk.?in|walk in|no appointment|drop.?in|same.?day)\b', text_lower, re.I):
        badges.append("Walk-in")
    
    # Interpreter available
    if re.search(r'\b(interpreter|translation|bilingual|language services|multilingual)\b', text_lower, re.I):
        badges.append("Interpreter Available")
    
    # 24/7 / Emergency
    if re.search(r'\b(24/7|24 hours|always open|emergency|round.?the.?clock)\b', text_lower, re.I):
        badges.append("24/7 Available")
    
    # Appointment required
    if re.search(r'\b(appointment required|call ahead|schedule|booking)\b', text_lower, re.I):
        badges.append("Appointment Required")
    
    return list(set(badges))  # Remove duplicates

def get_subcategories(services_text: str, category: str) -> List[str]:
    """Extract subcategories based on category and services description."""
    if not services_text:
        return []
    
    subcategories = []
    services_lower = services_text.lower()
    
    if category == "Healthcare":
        if re.search(r'\b(family medicine|primary care|internal medicine|general)\b', services_lower, re.I):
            subcategories.append("Primary Care")
        if re.search(r'\b(dental|dentist|oral)\b', services_lower, re.I):
            subcategories.append("Dental")
        if re.search(r'\b(pediatric|children|kids|adolescent|youth)\b', services_lower, re.I):
            subcategories.append("Pediatrics")
        if re.search(r'\b(women|obstetrics|gynecology|ob/gyn|prenatal|midwifery)\b', services_lower, re.I):
            subcategories.append("Women's Health")
        if re.search(r'\b(mental|therapy|counseling|psychiatric|behavioral)\b', services_lower, re.I):
            subcategories.append("Mental Health")
        if re.search(r'\b(mobile|screening|immunization|vaccination)\b', services_lower, re.I):
            subcategories.append("Mobile/Screening Services")
        if re.search(r'\b(hiv|sti|std)\b', services_lower, re.I):
            subcategories.append("HIV/STI Services")
        if re.search(r'\bryan\s*white\b|\bhrsa\s*hab\b', services_lower, re.I):
            if "Ryan White HIV/AIDS Program" not in subcategories:
                subcategories.insert(0, "Ryan White HIV/AIDS Program")
        if re.search(r'\b(nutrition)\b', services_lower, re.I):
            subcategories.append("Nutrition")
        if re.search(r'\b(urgent|emergency|24/7|24 hours)\b', services_lower, re.I):
            subcategories.append("Urgent Care")
        if re.search(r'\b(surgery|podiatry|specialty)\b', services_lower, re.I):
            subcategories.append("Specialty Care")
    
    elif category == "Education":
        if re.search(r'\b(esl|english language|english classes)\b', services_lower, re.I):
            subcategories.append("ESL Classes")
        if re.search(r'\b(citizenship|civics)\b', services_lower, re.I):
            subcategories.append("Citizenship Preparation")
        if re.search(r'\b(ged|high school|diploma|adult education)\b', services_lower, re.I):
            subcategories.append("GED Preparation")
        if re.search(r'\b(literacy|reading)\b', services_lower, re.I):
            subcategories.append("Adult Literacy")
        if re.search(r'\b(youth|after.?school|tutoring|homework help)\b', services_lower, re.I):
            subcategories.append("Youth Tutoring")
        if re.search(r'\b(computer|digital|technology)\b', services_lower, re.I):
            subcategories.append("Computer Literacy")
        if re.search(r'\b(workforce|job training|employment|career|vocational)\b', services_lower, re.I):
            subcategories.append("Workforce Development")
        if re.search(r'\b(financial literacy|financial)\b', services_lower, re.I):
            subcategories.append("Financial Literacy")
    
    elif category == "Resettlement / Legal / Shelter":
        if re.search(r'\b(refugee resettlement|resettlement|case management)\b', services_lower, re.I):
            subcategories.append("Refugee Resettlement")
        if re.search(r'\b(legal|lawyer|attorney|immigration|asylum|daca)\b', services_lower, re.I):
            subcategories.append("Legal Services")
        if re.search(r'\b(shelter|housing|homeless|emergency housing)\b', services_lower, re.I):
            subcategories.append("Emergency Shelter/Housing")
        if re.search(r'\b(employment|job|job placement|job training)\b', services_lower, re.I):
            subcategories.append("Employment Assistance")
        if re.search(r'\b(benefits|snap|medicaid|cash assistance|public benefits)\b', services_lower, re.I):
            subcategories.append("Public Benefits")
        if re.search(r'\b(food|food pantry|food bank|free meals)\b', services_lower, re.I):
            subcategories.append("Food Assistance")
        if re.search(r'\b(domestic violence|abuse|crisis)\b', services_lower, re.I):
            subcategories.append("Crisis Services")
    
    return list(set(subcategories))  # Remove duplicates

def normalize_languages(languages_text: str) -> List[str]:
    """Normalize and categorize languages (preserve order: English first when present)."""
    if not languages_text:
        return []

    languages = []
    seen = set()
    languages_lower = languages_text.lower()

    for lang_type, pattern in LANGUAGE_PATTERNS.items():
        if pattern.search(languages_lower) and lang_type not in seen:
            seen.add(lang_type)
            languages.append(lang_type)

    return languages

def convert_to_24h(hour: int, minute: int, ampm: str) -> tuple:
    """Convert 12-hour time to 24-hour format."""
    ampm = (ampm or "").lower().strip()
    
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    # If no am/pm specified, assume PM for hours 1-7 (common business hours)
    elif not ampm and 1 <= hour <= 7:
        hour += 12
    
    return (hour, minute)

def parse_hours(hours_text: str) -> Dict[str, List[tuple]]:
    """Parse hours text into structured format."""
    if not hours_text:
        return {}
    
    hours_dict = {}
    hours_lower = hours_text.lower()
    
    # Time pattern that captures hour, optional minutes, and optional am/pm
    time_pattern = re.compile(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', re.I)
    
    for day, pattern in DAY_PATTERNS.items():
        if pattern.search(hours_lower):
            # Extract time ranges for this day
            day_text = pattern.search(hours_lower)
            if day_text:
                start_pos = day_text.end()
                # Look for time patterns after the day
                remaining = hours_lower[start_pos:start_pos+50]  # Look ahead 50 chars
                times = time_pattern.findall(remaining)
                
                if times:
                    # Convert to time objects with proper 24-hour conversion
                    time_ranges = []
                    for i in range(0, len(times), 2):
                        if i+1 < len(times):
                            start_time = times[i]
                            end_time = times[i+1]
                            
                            # Parse start time
                            start_hour = int(start_time[0])
                            start_min = int(start_time[1]) if start_time[1] else 0
                            start_ampm = start_time[2] if len(start_time) > 2 else ""
                            
                            # Parse end time
                            end_hour = int(end_time[0])
                            end_min = int(end_time[1]) if end_time[1] else 0
                            end_ampm = end_time[2] if len(end_time) > 2 else ""
                            
                            # Convert to 24-hour format
                            start_24h = convert_to_24h(start_hour, start_min, start_ampm)
                            end_24h = convert_to_24h(end_hour, end_min, end_ampm)
                            
                            time_ranges.append((start_24h, end_24h))
                    
                    hours_dict[day] = time_ranges
    
    return hours_dict

def parse_blocks(text: str, category: str = "") -> List[Dict[str, Any]]:
    """Parse text blocks into structured records."""
    items = []
    
    # Split by numbered items (format: "1. Name" or "NN. Name")
    # Also handle double newlines as separators
    # First, normalize: split by double newlines OR by numbered item patterns
    text_clean = text.strip()
    
    # Try splitting by numbered items first (more reliable)
    blocks = re.split(r'(?:\n\s*\n+|\n)(?=\d+\.\s)', text_clean)
    
    # If that doesn't work well, fall back to double newlines
    if len(blocks) < 2:
        blocks = re.split(r'\n\s*\n+', text_clean)
    
    for block in blocks:
        if not block.strip():
            continue
            
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 2:
            continue
        
        # Extract name (usually first line, may have "NN. " prefix)
        first_line = lines[0].strip()
        name = re.sub(r'^\d+\.\s*', '', first_line).strip()
        
        # Try to extract item ID from first line if present
        id_match = re.match(r'^(\d+)\.\s', first_line)
        item_id = id_match.group(1) if id_match else f"item_{len(items) + 1}"
        
        # Initialize record
        record = {
            "id": item_id,
            "name": name,
            "address": "",
            "phone": "",
            "phone_digits": "",
            "website": "",
            "zip_code": "",
            "services": [],
            "services_text": "",  # Store original services text
            "subcategories": [],  # Store subcategories
            "availability_badges": [],  # Store availability badges
            "languages": [],
            "hours": {},
            "hours_text": "",
            "notes": "",
            "search_blob": "",  # Precomputed for fast search
        }
        
        # Parse other fields
        for line in lines[1:]:
            line_lower = line.lower()
            
            if any(keyword in line_lower for keyword in ['services:', '🏥', '🛟', '🛠️']):
                services_text = re.sub(r'^(services?|🏥|🛟|🛠️):\s*', '', line, flags=re.I).strip()
                record["services_text"] = services_text
                record["services"] = normalize_services(services_text)
                # Extract subcategories based on category
                if category:
                    record["subcategories"] = get_subcategories(services_text, category)
                # Extract availability badges
                record["availability_badges"] = get_availability_badges(services_text, record["name"], record["address"])
            
            elif any(keyword in line_lower for keyword in ['phone:', '📞']) or line.strip().startswith('📞'):
                phone_text = re.sub(r'^(?:📞|phone)\s*:?\s*', '', line, flags=re.I).strip()
                phone_data = normalize_phone(phone_text)
                record["phone"] = phone_data["phone"]
                record["phone_digits"] = phone_data["phone_digits"]
            
            elif any(keyword in line_lower for keyword in ['hours:', '⏰']):
                # Strip "⏰ Hours:", "Hours:", "⏰:" etc. so UI can add its own label
                hours_text = re.sub(
                    r'^(?:⏰\s*)?Hours?:\s*',
                    '',
                    line,
                    flags=re.I,
                ).strip()
                hours_text = re.sub(r'^⏰\s*', '', hours_text).strip()
                record["hours"] = parse_hours(hours_text)
                record["hours_text"] = hours_text

            # Website BEFORE languages: 🌐 is the website marker (languages use 🗣)
            elif any(keyword in line_lower for keyword in ['website:', 'web:']) or (
                line.strip().startswith('🌐') or ('http://' in line_lower or 'https://' in line_lower)
            ):
                web_text = re.sub(r'^(?:website|🌐|web)\s*:?\s*', '', line, flags=re.I).strip()
                record["website"] = normalize_website(web_text)
            
            elif any(keyword in line_lower for keyword in ['languages:', '🗣', 'language:']) or line.strip().startswith('🗣'):
                lang_text = re.sub(r'^(?:languages?|🗣|language)\s*:?\s*', '', line, flags=re.I).strip()
                record["languages"] = normalize_languages(lang_text)

            elif line.strip().startswith('📝') or line_lower.startswith('note'):
                note = re.sub(r'^(📝|notes?)\s*:?\s*', '', line, flags=re.I).strip()
                record["notes"] = note
                # Ryan White / HAB context from HRSA notes
                if re.search(r'ryan\s*white|hrsa\s*hab', note, re.I):
                    if "Ryan White HIV/AIDS Program" not in record["subcategories"]:
                        record["subcategories"].insert(0, "Ryan White HIV/AIDS Program")
                    if "hiv_sti" not in record["services"]:
                        record["services"].append("hiv_sti")
            
            elif any(keyword in line_lower for keyword in ['address:', '📍', 'location:']):
                addr_text = normalize_address(line)
                # If the whole line was only "📍", fall back
                if not addr_text:
                    addr_text = normalize_address(re.sub(r'^(address|📍|location):\s*', '', line, flags=re.I))
                record["address"] = addr_text
                record["zip_code"] = normalize_zip(addr_text)
            
            else:
                # Check if line starts with 📍 emoji (address indicator)
                if line.strip().startswith('📍'):
                    addr_text = normalize_address(line)
                    record["address"] = addr_text
                    record["zip_code"] = normalize_zip(addr_text)
                # Assume it's address if no keyword found and looks like an address
                elif not record["address"] and len(line) > 10 and ('chicago' in line_lower or 'il' in line_lower or re.search(r'\b(60\d{3})\b', line)):
                    record["address"] = normalize_address(line)
                    record["zip_code"] = normalize_zip(record["address"])
        
        # Precompute search blob for fast searching (include subcategories and services text)
        search_fields = [
            record["name"],
            record["address"],
            record["services_text"],  # Include full services text for better semantic matching
            " ".join(record["services"]),
            " ".join(record["subcategories"]),  # Include subcategories
            " ".join(record["languages"]),
            record["hours_text"],
            record.get("notes") or "",
            record.get("phone") or "",
            record.get("website") or "",
        ]
        record["search_blob"] = " ".join([f for f in search_fields if f]).lower()
        
        items.append(record)
    
    return items

# ===========================
# Cached Data Loading
# ===========================

@st.cache_data(ttl=600, show_spinner=False)
def load_category_data(
    category: str,
    force_refresh: bool = False,
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load category data for a USPS state (default RESOURCES_STATE / IL).
    Prefer local JSON for speed; refresh from GitHub when forced or missing.
    """
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    try:
        from agents.geo_scope import data_sources as _ds, resources_state as _rs
    except Exception:
        _ds = None
        _rs = None

    st_code = (state or (_rs() if _rs else None) or "IL").strip().upper() or "IL"
    category_key = category.lower().replace(" / ", "_").replace(" ", "_")
    json_path = data_dir / f"{category_key}_{st_code}.json"
    # Legacy single-state cache (older WhatWay installs wrote healthcare.json for IL)
    legacy_path = data_dir / f"{category_key}.json"

    if not force_refresh:
        for path in (json_path, legacy_path if st_code == "IL" else None):
            if path is None or not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    return data
            except Exception as e:
                print(f"Error loading cached JSON ({path}): {e}")

    sources_map = _ds(st_code) if _ds else DATA_SOURCES
    sources = sources_map.get(category, [])
    github_urls = [s for s in sources if s.startswith("http")]
    local_files = [s for s in sources if not s.startswith("http")]

    raw_text = None
    for source in github_urls + local_files:
        try:
            raw_text = fetch_text_from_sources([source])
            if raw_text:
                break
        except Exception:
            continue

    if not raw_text:
        return []

    items = parse_blocks(raw_text, category)
    for it in items:
        if isinstance(it, dict) and not it.get("state"):
            it["state"] = st_code
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"✅ Updated {json_path} from GitHub .txt file ({len(items)} items)")
    except Exception as e:
        print(f"Error saving normalized JSON: {e}")

    return items

@st.cache_resource
def get_compiled_patterns():
    """Return compiled regex patterns for caching."""
    return {
        "zip": ZIP_PATTERN,
        "phone": PHONE_PATTERN,
        "email": EMAIL_PATTERN,
        "website": WEBSITE_PATTERN,
        "services": SERVICE_PATTERNS,
        "languages": LANGUAGE_PATTERNS,
        "days": DAY_PATTERNS,
    }

# ===========================
# Public API
# ===========================

def get_dataset(category: str, state: Optional[str] = None) -> tuple:
    """Get dataset for a category (+ optional USPS state). Returns (items, raw_text stub)."""
    items = load_category_data(category, state=state)
    return items, ""


def refresh_category_cache(category: str, state: Optional[str] = None) -> None:
    """Force refresh of category cache from GitHub .txt → local JSON."""
    try:
        from agents.geo_scope import resources_state as _rs
        st_code = (state or _rs() or "IL").strip().upper()
    except Exception:
        st_code = (state or "IL").strip().upper() or "IL"
    category_key = category.lower().replace(" / ", "_").replace(" ", "_")
    json_path = Path("data") / f"{category_key}_{st_code}.json"
    legacy_path = Path("data") / f"{category_key}.json"

    for path in (json_path, legacy_path if st_code == "IL" else None):
        if path and path.exists():
            path.unlink()

    clear_fn = getattr(load_category_data, "clear", None)
    if callable(clear_fn):
        try:
            clear_fn()
        except Exception:
            pass

    load_category_data(category, force_refresh=True, state=st_code)


