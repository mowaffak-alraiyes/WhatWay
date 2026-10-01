#!/usr/bin/env python3
"""
Optional LLM service for intent, short replies, summarization, and translation.

Search remains deterministic. The LLM never chooses or invents resources; it
only works with the query and records already retrieved by WhatWay.
"""

import os as _os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import streamlit as st
from openai import OpenAI

# ===========================
# Configuration
# ===========================

OLLAMA_MODEL = _os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_BASE_URL = _os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
WORKERS_AI_MODEL = _os.environ.get(
    "CLOUDFLARE_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct"
)

_ACTIVE_PROVIDER: Optional[str] = None
_ACTIVE_MODEL: Optional[str] = None

# System prompts for different tasks
INTENT_SYSTEM_PROMPT = """You are a helpful assistant for a refugee resource finder in Chicago.
Your job is to understand what the user is looking for and extract structured information.

Given a user query, extract:
1. category: One of "Healthcare", "Education", or "Resettlement / Legal / Shelter"
2. service_type: Specific service needed (e.g., "dental", "pediatric", "ESL", "legal", "shelter")
3. filters: Any mentioned filters like ZIP code, language, day of week
4. urgency: Is this urgent? (true/false)
5. language: What language is the user writing in?

Respond ONLY with valid JSON in this exact format:
{
    "category": "Healthcare|Education|Resettlement / Legal / Shelter",
    "service_type": "specific service or null",
    "zip_code": "60xxx or null",
    "language_filter": "language or null", 
    "day_filter": "day of week or null",
    "urgency": true|false,
    "user_language": "English|Spanish|Arabic|etc",
    "cleaned_query": "simplified search terms",
    "understood_need": "brief description of what user needs"
}"""

RESPONSE_SYSTEM_PROMPT = """You are Pip, a friendly little robot helper for WhatWay.
You help refugees and immigrants find Chicago community resources.

Rules:
- Speak as Pip in ONE short, warm sentence (max 18 words)
- Sound encouraging and human-friendly, not corporate
- Do not list clinics (cards show them)
- No medical/legal advice or promises"""

SUMMARY_SYSTEM_PROMPT = """You are helping summarize community resources for refugees and immigrants.
Create a brief, friendly one-sentence summary of each resource that highlights:
- What makes it useful for the person
- Key services offered
- Any special features (free, walk-in, languages spoken)

Keep summaries under 20 words, use simple English."""

TRANSLATION_SYSTEM_PROMPT = """You are a translator helping refugees access community resources.
Translate the following text accurately while keeping it simple and clear.
Maintain a warm, helpful tone. Keep formatting intact."""


# ===========================
# Client Initialization
# ===========================

def _secret(key: str) -> Optional[str]:
    val = _os.environ.get(key)
    if val:
        return val
    try:
        return st.secrets.get(key)
    except Exception:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def _ollama_reachable() -> bool:
    try:
        import urllib.request

        base = (_secret("OLLAMA_BASE_URL") or OLLAMA_BASE_URL).rstrip("/")
        native = base.replace("/v1", "") + "/api/tags"
        with urllib.request.urlopen(native, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_llm_client() -> Optional[OpenAI]:
    """Return the configured OpenAI-compatible client.

    Ollama is the default for local development. Workers AI is the production
    option and uses Cloudflare's OpenAI-compatible endpoint. Setting the
    provider to ``none`` keeps every user-facing search path fully functional.
    """
    global _ACTIVE_PROVIDER, _ACTIVE_MODEL

    provider = (_secret("WHATWAY_LLM_PROVIDER") or "ollama").strip().lower()

    if provider in {"none", "off", "disabled"}:
        _ACTIVE_PROVIDER = None
        _ACTIVE_MODEL = None
        return None

    if provider in {"workers_ai", "cloudflare", "cloudflare_workers_ai"}:
        account_id = _secret("CLOUDFLARE_ACCOUNT_ID")
        api_token = _secret("CLOUDFLARE_AI_TOKEN")
        model = _secret("CLOUDFLARE_AI_MODEL") or WORKERS_AI_MODEL
        if not account_id or not api_token:
            _ACTIVE_PROVIDER = None
            _ACTIVE_MODEL = None
            return None
        _ACTIVE_PROVIDER = "workers_ai"
        _ACTIVE_MODEL = model
        return OpenAI(
            base_url=(
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{account_id}/ai/v1"
            ),
            api_key=api_token,
        )

    ollama_model = _secret("OLLAMA_MODEL") or OLLAMA_MODEL
    ollama_base = _secret("OLLAMA_BASE_URL") or OLLAMA_BASE_URL

    if not _ollama_reachable():
        _ACTIVE_PROVIDER = None
        _ACTIVE_MODEL = None
        return None

    _ACTIVE_PROVIDER = "ollama"
    _ACTIVE_MODEL = ollama_model
    return OpenAI(base_url=ollama_base, api_key="ollama")


def get_active_model(fast: bool = True) -> str:
    if _ACTIVE_MODEL:
        return _ACTIVE_MODEL
    provider = (_secret("WHATWAY_LLM_PROVIDER") or "ollama").strip().lower()
    if provider in {"workers_ai", "cloudflare", "cloudflare_workers_ai"}:
        return _secret("CLOUDFLARE_AI_MODEL") or WORKERS_AI_MODEL
    return _secret("OLLAMA_MODEL") or OLLAMA_MODEL


def llm_status() -> dict:
    client = get_llm_client()
    configured_provider = (
        _secret("WHATWAY_LLM_PROVIDER") or "ollama"
    ).strip().lower()
    return {
        "available": client is not None,
        "provider": _ACTIVE_PROVIDER,
        "configured_provider": configured_provider,
        "model": (_ACTIVE_MODEL or get_active_model()) if client else None,
    }


def is_llm_available() -> bool:
    return get_llm_client() is not None


# ===========================
# Intent Detection
# ===========================

def detect_intent(query: str) -> Dict:
    """
    Use LLM to understand user intent and extract structured information.
    
    Returns:
        Dict with extracted intent information, or None if LLM unavailable.
    """
    client = get_llm_client()
    
    if not client:
        # Return default/fallback when LLM not available
        return {
            "category": None,
            "service_type": None,
            "zip_code": None,
            "language_filter": None,
            "day_filter": None,
            "urgency": False,
            "user_language": "English",
            "cleaned_query": query,
            "understood_need": query,
            "llm_available": False
        }
    
    try:
        response = client.chat.completions.create(
            model=get_active_model(fast=True),  # Use fast model for intent detection
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        result = json.loads(result_text)
        result["llm_available"] = True
        return result
        
    except Exception as e:
        print(f"Intent detection error: {e}")
        return {
            "category": None,
            "service_type": None,
            "zip_code": None,
            "language_filter": None,
            "day_filter": None,
            "urgency": False,
            "user_language": "English",
            "cleaned_query": query,
            "understood_need": query,
            "llm_available": False,
            "error": str(e)
        }


# ===========================
# Conversational Responses
# ===========================

def generate_response(
    query: str,
    results: List[Dict],
    category: str,
    context: Optional[List[Dict]] = None
) -> str:
    """
    Generate a warm, conversational response based on search results.
    
    Args:
        query: User's original query
        results: List of resource results
        category: Category searched
        context: Previous conversation messages for follow-ups
    
    Returns:
        Friendly response text
    """
    client = get_llm_client()
    
    if not client:
        # Fallback to template response
        if results:
            return f"I found {len(results)} {category.lower()} options that look helpful!"
        else:
            return "Hmm, nothing exact - try another ZIP or service and I’ll dig again."
    
    user_message = f"""User searched for: "{query}"
Category: {category}
Results: {len(results)}
Top names: {', '.join(r.get('name','') for r in results[:3]) or 'none'}

Write ONE short Pip sentence introducing these results (warm, friendly)."""

    messages = [{"role": "system", "content": RESPONSE_SYSTEM_PROMPT}]
    
    # Add conversation context if provided
    if context:
        for msg in context[-4:]:  # Last 4 messages for context
            messages.append(msg)
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model=get_active_model(fast=True),
            messages=messages,
            temperature=0.5,
            max_tokens=60
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Response generation error: {e}")
        if results:
            return f"Here are {len(results)} {category.lower()} options for you."
        else:
            return "No exact matches - try another ZIP or service."


# ===========================
# Resource Summarization
# ===========================

@st.cache_data(ttl=3600, show_spinner=False)
def summarize_resource(resource: Dict, user_need: str = "") -> str:
    """
    Generate a brief, friendly summary of a resource.
    
    Args:
        resource: Resource dictionary
        user_need: What the user is looking for (for relevance)
    
    Returns:
        One-sentence summary
    """
    client = get_llm_client()
    
    if not client:
        # Fallback to basic summary
        name = resource.get("name", "This resource")
        services = resource.get("services", [])
        if isinstance(services, list) and services:
            return f"{name} offers {', '.join(services[:2])}."
        return f"{name} may be able to help you."
    
    # Build resource description
    resource_info = f"""
Name: {resource.get('name', 'Unknown')}
Services: {resource.get('services_text', '') or ', '.join(resource.get('services', []))}
Languages: {', '.join(resource.get('languages', [])) if isinstance(resource.get('languages'), list) else resource.get('languages', '')}
Address: {resource.get('address', '')}
"""
    
    user_message = f"""Summarize this resource in ONE simple sentence (under 20 words):
{resource_info}

User is looking for: {user_need if user_need else 'community resources'}"""

    try:
        response = client.chat.completions.create(
            model=get_active_model(fast=True),
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.5,
            max_tokens=50
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Summarization error: {e}")
        name = resource.get("name", "This resource")
        return f"{name} offers community services that may help you."


# ===========================
# Translation & Multilingual
# ===========================

# Supported languages for translation
SUPPORTED_LANGUAGES = {
    "english": "en",
    "spanish": "es",
    "arabic": "ar",
    "french": "fr",
    "polish": "pl",
    "mandarin": "zh",
    "chinese": "zh",
    "urdu": "ur",
    "hindi": "hi",
    "ukrainian": "uk",
    "swahili": "sw",
    "tigrinya": "ti"
}


def detect_language(text: str) -> str:
    """
    Detect the language of user input.
    
    Returns:
        Language name (e.g., "Spanish", "Arabic")
    """
    client = get_llm_client()
    
    if not client:
        return "English"  # Default assumption
    
    try:
        response = client.chat.completions.create(
            model=get_active_model(fast=True),
            messages=[
                {"role": "system", "content": "Detect the language of the following text. Respond with ONLY the language name in English (e.g., 'Spanish', 'Arabic', 'English')."},
                {"role": "user", "content": text}
            ],
            temperature=0,
            max_tokens=20
        )
        
        detected = response.choices[0].message.content.strip()
        # Clean up response
        detected = detected.replace(".", "").replace(",", "").strip()
        return detected.title()
        
    except Exception:
        return "English"


@st.cache_data(ttl=3600, show_spinner=False)
def translate_text(text: str, target_language: str, source_language: str = "English") -> str:
    """
    Translate text to target language.
    
    Args:
        text: Text to translate
        target_language: Target language name
        source_language: Source language name
    
    Returns:
        Translated text
    """
    if target_language.lower() == source_language.lower():
        return text
    
    client = get_llm_client()
    
    if not client:
        return text  # Return original if LLM unavailable
    
    try:
        response = client.chat.completions.create(
            model=get_active_model(fast=True),
            messages=[
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Translate from {source_language} to {target_language}:\n\n{text}"}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Translation error: {e}")
        return text


def translate_response_if_needed(
    response: str,
    user_language: str,
    include_english: bool = True
) -> str:
    """
    Translate response to user's language if not English.
    
    Args:
        response: Response text in English
        user_language: User's detected language
        include_english: Whether to include English version too
    
    Returns:
        Translated response (optionally with English)
    """
    if user_language.lower() in ["english", "en"]:
        return response
    
    translated = translate_text(response, user_language, "English")
    
    if include_english and translated != response:
        return f"{translated}\n\n---\n*In English:* {response}"
    
    return translated


# ===========================
# Follow-up Handling
# ===========================

def is_follow_up_query(query: str, previous_results: List[Dict]) -> Tuple[bool, str]:
    """
    Detect if the query is a follow-up to previous results.
    
    Args:
        query: Current user query
        previous_results: Results from previous search
    
    Returns:
        Tuple of (is_follow_up, follow_up_type)
    """
    query_lower = query.lower().strip()
    
    # Common follow-up patterns
    follow_up_patterns = {
        "more": "more_results",
        "show more": "more_results",
        "next": "more_results",
        "open now": "filter_time",
        "open today": "filter_time",
        "which are open": "filter_time",
        "any open": "filter_time",
        "free": "filter_free",
        "which are free": "filter_free",
        "closest": "filter_distance",
        "nearest": "filter_distance",
        "spanish": "filter_language",
        "speaks spanish": "filter_language",
        "arabic": "filter_language",
        "walk-in": "filter_walkin",
        "walk in": "filter_walkin",
        "no appointment": "filter_walkin",
        "tell me more": "detail_request",
        "more about": "detail_request",
        "first one": "select_result",
        "second one": "select_result",
        "third one": "select_result",
        "the first": "select_result",
        "the second": "select_result",
    }
    
    for pattern, follow_up_type in follow_up_patterns.items():
        if pattern in query_lower:
            return True, follow_up_type
    
    # Check if it's a very short query (likely follow-up)
    if len(query_lower.split()) <= 3 and previous_results:
        return True, "possible_filter"
    
    return False, ""


def handle_follow_up(
    query: str,
    follow_up_type: str,
    previous_results: List[Dict],
    all_results: List[Dict]
) -> Tuple[List[Dict], str]:
    """
    Handle follow-up queries by filtering or expanding results.
    
    Args:
        query: Follow-up query
        follow_up_type: Type of follow-up detected
        previous_results: Results already shown
        all_results: All matching results
    
    Returns:
        Tuple of (filtered_results, explanation)
    """
    import search
    
    if follow_up_type == "more_results":
        # Get next batch of results
        shown_ids = {r.get("id") for r in previous_results}
        new_results = [r for r in all_results if r.get("id") not in shown_ids][:3]
        return new_results, "Here are more options for you!"
    
    elif follow_up_type == "filter_time":
        # Filter to currently open
        open_results = [r for r in all_results if search.is_open_now(r)]
        if open_results:
            return open_results[:5], f"I found {len(open_results)} places open right now!"
        else:
            return [], "Unfortunately, none of the matching places are open right now."
    
    elif follow_up_type == "filter_free":
        # Filter to free services
        free_results = [r for r in all_results 
                       if "Free" in r.get("availability_badges", [])]
        if free_results:
            return free_results[:5], f"Here are {len(free_results)} free options!"
        else:
            return all_results[:3], "I couldn't find specifically free options, but these may offer sliding scale fees."
    
    elif follow_up_type == "filter_walkin":
        # Filter to walk-in
        walkin_results = [r for r in all_results 
                        if "Walk-in" in r.get("availability_badges", [])]
        if walkin_results:
            return walkin_results[:5], "These places accept walk-ins - no appointment needed!"
        else:
            return all_results[:3], "I couldn't find walk-in specific options. You may want to call ahead."
    
    elif follow_up_type == "filter_language":
        # Extract language from query and filter
        for lang in SUPPORTED_LANGUAGES.keys():
            if lang in query.lower():
                lang_results = [r for r in all_results 
                               if lang in str(r.get("languages", [])).lower()]
                if lang_results:
                    return lang_results[:5], f"These places have {lang.title()} speakers!"
                break
        return all_results[:3], "Let me show you some options. Call to confirm language availability."
    
    elif follow_up_type == "select_result":
        # Handle "tell me about the first one"
        number_words = {"first": 0, "second": 1, "third": 2, "1": 0, "2": 1, "3": 2}
        for word, idx in number_words.items():
            if word in query.lower():
                if idx < len(previous_results):
                    return [previous_results[idx]], f"Here's more about {previous_results[idx].get('name', 'this resource')}:"
        return previous_results[:1], "Here's more information:"
    
    # Default: return previous results
    return previous_results, ""


# ===========================
# Conversation Context Manager
# ===========================

class ConversationContext:
    """Manages conversation context for follow-up handling."""
    
    def __init__(self):
        self.messages: List[Dict] = []
        self.last_results: List[Dict] = []
        self.last_all_results: List[Dict] = []
        self.last_category: str = ""
        self.last_query: str = ""
        self.user_language: str = "English"
    
    def add_user_message(self, query: str):
        """Add user message to context."""
        self.messages.append({"role": "user", "content": query})
        self.last_query = query
        # Keep only last 10 messages
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]
    
    def add_assistant_message(self, response: str):
        """Add assistant response to context."""
        self.messages.append({"role": "assistant", "content": response})
    
    def set_results(self, shown_results: List[Dict], all_results: List[Dict], category: str):
        """Store search results for follow-up handling."""
        self.last_results = shown_results
        self.last_all_results = all_results
        self.last_category = category
    
    def get_context_messages(self) -> List[Dict]:
        """Get messages for LLM context."""
        return self.messages[-6:]  # Last 6 messages
    
    def clear(self):
        """Clear conversation context."""
        self.messages = []
        self.last_results = []
        self.last_all_results = []
        self.last_category = ""
        self.last_query = ""


def get_conversation_context() -> ConversationContext:
    """Get or create conversation context from session state."""
    if "llm_conversation_context" not in st.session_state:
        st.session_state["llm_conversation_context"] = ConversationContext()
    return st.session_state["llm_conversation_context"]


# ===========================
# Main LLM Processing Function
# ===========================

def process_query_with_llm(
    query: str,
    current_category: str
) -> Dict:
    """
    Main function to process a user query with LLM assistance.
    
    Args:
        query: User's query
        current_category: Currently selected category
    
    Returns:
        Dict with:
        - intent: Detected intent information
        - category: Recommended category
        - service_type: Detected service type
        - filters: Detected filters (zip, language, day)
        - is_follow_up: Whether this is a follow-up
        - follow_up_type: Type of follow-up if applicable
        - user_language: Detected user language
    """
    context = get_conversation_context()
    
    # Check if this is a follow-up query
    is_follow_up, follow_up_type = is_follow_up_query(query, context.last_results)
    
    if is_follow_up and follow_up_type != "possible_filter":
        return {
            "intent": None,
            "category": context.last_category or current_category,
            "service_type": None,
            "filters": {},
            "is_follow_up": True,
            "follow_up_type": follow_up_type,
            "user_language": context.user_language,
            "cleaned_query": query
        }
    
    # Detect intent using LLM
    intent = detect_intent(query)
    
    # Update user language in context
    if intent.get("user_language"):
        context.user_language = intent["user_language"]
    
    # Build filters dict
    filters = {}
    if intent.get("zip_code"):
        filters["zip"] = intent["zip_code"]
    if intent.get("language_filter"):
        filters["language"] = intent["language_filter"]
    if intent.get("day_filter"):
        filters["day"] = intent["day_filter"]
    
    return {
        "intent": intent,
        "category": intent.get("category") or current_category,
        "service_type": intent.get("service_type"),
        "filters": filters,
        "is_follow_up": is_follow_up,
        "follow_up_type": follow_up_type,
        "user_language": intent.get("user_language", "English"),
        "cleaned_query": intent.get("cleaned_query", query),
        "understood_need": intent.get("understood_need", query),
        "urgency": intent.get("urgency", False)
    }
