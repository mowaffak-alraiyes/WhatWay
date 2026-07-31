#!/usr/bin/env python3
"""
Optimized Community Resources Chat App
Using modular components for better performance and maintainability.
"""

import streamlit as st
import uuid
import database as db
from typing import List, Dict, Tuple
import data_loader
import search
import ui_components

# ===========================
# Page Configuration
# ===========================
st.set_page_config(page_title="Community Resources Chat", layout="wide")

# Initialize database
db.initialize_database()

# ===========================
# Styles
# ===========================
ui_components.render_mobile_friendly_category_selector()

# ===========================
# Constants
# ===========================
TOP_N = 10  # Show more results initially
MORE_N = 10  # Show this many more when "Show More" is clicked

# ===========================
# Session State
# ===========================
st.session_state.setdefault("category", "Healthcare")
st.session_state.setdefault("datasets_cache", {})
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pinned", [])
st.session_state.setdefault("last_query_by_cat", {})
st.session_state.setdefault("shown_ids_by_cat", {})
st.session_state.setdefault("scroll_flag", False)
st.session_state.setdefault("misspelling_suggestion", None)
st.session_state.setdefault("waiting_for_misspelling_response", False)
st.session_state.setdefault("show_more", False)

# Initialize conversation ID for database logging
if "convo_id" not in st.session_state:
    st.session_state["convo_id"] = uuid.uuid4().hex[:12]

# ===========================
# Sidebar
# ===========================
with st.sidebar:
    st.header("🔧 Controls")
    
    # Category selection
    st.subheader("📂 Category")
    category = st.radio(
        "Choose a category:",
        ["Healthcare", "Education", "Resettlement / Legal / Shelter"],
        key="category_selector"
    )
    
    if category != st.session_state["category"]:
        st.session_state["category"] = category
        st.session_state["shown_ids_by_cat"][category] = []
        st.session_state["show_more"] = False
        st.rerun()
    
    # Load data for current category
    items, raw_text = data_loader.get_dataset(category)
    
    # Enhanced filters
    zip_filter, lang_filter, service_filter, day_filter = ui_components.render_enhanced_filters(category, items)
    
    # Reset and refresh controls
    st.subheader("🔄 Actions")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Reset Chat"):
            st.session_state["messages"] = []
            st.session_state["pinned"] = []
            st.session_state["last_query_by_cat"] = {}
            st.session_state["shown_ids_by_cat"] = {}
            st.session_state["scroll_flag"] = False
            st.session_state["misspelling_suggestion"] = None
            st.session_state["waiting_for_misspelling_response"] = False
            st.session_state["datasets_cache"] = {}
            st.session_state["convo_id"] = uuid.uuid4().hex[:12]
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh Data"):
            data_loader.refresh_category_cache(category)
            st.success("Data refreshed!")
            st.rerun()
    
    # Scroll control
    if st.button("⏬ Scroll to Latest"):
        st.session_state["scroll_flag"] = True
        st.rerun()
    
    # Pinned resources
    ui_components.render_pinned_sidebar()
    
    # QR Code section
    ui_components.render_qr_section()
    
    # Tips
    st.subheader("💡 Tips")
    if len(day_filter) > 1:
        st.info("💡 **Smart search:** Try 'dental 60629', 'ESL monday', 'legal help mon', or 'clinic tue-thu'")
    else:
        st.info("💡 **Smart search:** Try 'dental 60629', 'ESL classes', or 'legal help'")

# ===========================
# Main Content
# ===========================

# Display chat history
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["text"])
        else:
            if "render" in message:
                # Render cards
                for i, result in enumerate(message["results"], 1):
                    ui_components.render_enhanced_card(i, result, message["category"])
            else:
                st.markdown(message["text"])

# ===========================
# Chat Input and Response
# ===========================

def respond_to_query(user_text: str, category: str):
    """Enhanced query response with better search and logging."""
    is_more = user_text.strip().lower() == "more"
    
    # Determine query
    if is_more:
        query = st.session_state["last_query_by_cat"].get(category, "")
        if not query:
            st.error("No previous query found. Please search for something first.")
            return
    else:
        query = user_text
        st.session_state["last_query_by_cat"][category] = query
    
    # Auto-detect filters from query
    detected_zip = None
    detected_service = None
    detected_day = None
    
    if not is_more:
        detected_zip = search.detect_zip_from_query(query)
        detected_service = search.detect_service_from_query(query, category)
        detected_day = search.detect_day_from_query(query)
        
        # Store detected filters for display
        st.session_state[f"detected_zip_{category}"] = detected_zip
        st.session_state[f"detected_service_{category}"] = detected_service
        st.session_state[f"detected_day_{category}"] = detected_day
        
        # Clean query
        query = search.clean_query_of_zip(query)
        query = search.clean_query_of_service_and_day(query, detected_service, detected_day)
    
    # Use detected filters or sidebar filters
    zf = detected_zip or zip_filter or "All"
    lf = lang_filter or "All"
    sf = detected_service or service_filter or "All"
    df = detected_day or day_filter or "All"
    
    # Enhanced search with fuzzy matching
    ranked = search.rank_items(items, query, category, zf, lf, sf, df)
    
    # Handle pagination
    shown_map = st.session_state["shown_ids_by_cat"]
    prev_ids = set(shown_map.get(category, []))
    
    if is_more or st.session_state.get("show_more", False):
        # Show more results
        fresh = [c for _, c in ranked if c["id"] not in prev_ids]
        to_show = fresh[:MORE_N]
        st.session_state["show_more"] = False
    else:
        # Show initial results
        fresh = [c for _, c in ranked if c["id"] not in prev_ids]
        to_show = fresh[:TOP_N]
    
    # Update shown IDs
    ids = [c["id"] for c in to_show]
    shown_map[category] = list(prev_ids | set(ids))
    
    # Display results
    with st.chat_message("assistant"):
        if to_show:
            # Friendly introduction
            intro_parts = [f"Great question! I found **{len(to_show)}** {category.lower()} resources"]
            
            if query:
                intro_parts.append(f"matching '{query}'")
            
            if detected_zip or detected_service or detected_day:
                detected_parts = []
                if detected_zip:
                    detected_parts.append(f"ZIP **{detected_zip}**")
                if detected_service:
                    detected_parts.append(f"**{detected_service}** services")
                if detected_day:
                    detected_parts.append(f"**{detected_day}** availability")
                
                if detected_parts:
                    intro_parts.append(f"with smart filtering for {', '.join(detected_parts)}")
            
            intro = " ".join(intro_parts) + ". Here are the best matches:"
            st.markdown(intro)
            
            # Show smart filtering info
            if detected_zip or detected_service or detected_day:
                st.info("🔍 **Smart filtering active** - I automatically detected your preferences!")
            
            # Render enhanced cards
            for i, item in enumerate(to_show, 1):
                ui_components.render_enhanced_card(i, item, category)
            
            # Pagination controls
            total_ranked = len(ranked)
            shown_count = len(shown_map.get(category, []))
            
            if ui_components.render_pagination_controls(total_ranked, shown_count):
                st.session_state["show_more"] = True
                st.rerun()
            
            # Proactive suggestions
            st.info("💡 **Want to narrow it down?** Tell me your ZIP code, preferred language, service type, or day of the week!")
            
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
            reply_json = {"category": category, "results": to_show, "query": query}
            db.save_assistant_message(
                convo_id=st.session_state["convo_id"],
                reply_text=reply_text,
                reply_json=reply_json,
                category=category
            )
            
            # Persist assistant message
            st.session_state["messages"].append({
                "role": "assistant",
                "render": "cards",
                "category": category,
                "results": to_show,
                "text": intro
            })
            
        else:
            # No results
            st.markdown(
                "😔 I couldn't find any matches for that search. "
                "Try different keywords or check these trusted resources: "
                "[FindHelp.org](https://www.findhelp.org), "
                "[211.org](https://www.211.org), or "
                "[HRSA Health Center Locator](https://findahealthcenter.hrsa.gov/)."
            )
            
            # Log no results
            reply_text = "No matches found for query"
            reply_json = {"category": category, "results": [], "query": query}
            db.save_assistant_message(
                convo_id=st.session_state["convo_id"],
                reply_text=reply_text,
                reply_json=reply_json,
                category=category
            )
            
            st.session_state["messages"].append({
                "role": "assistant",
                "text": "No matches found"
            })
        
        # Auto-scroll
        st.session_state["scroll_flag"] = True

# Chat input
prompt = st.chat_input(
    f"💬 What {category} resources are you looking for? (e.g., 'dental 60629', 'ESL monday', 'legal help')…"
)

if prompt:
    # Add user message to chat
    with st.chat_message("user"):
        st.markdown(prompt)
    
    st.session_state["messages"].append({"role": "user", "text": prompt})
    
    # Log user message to database
    db.save_user_message(
        convo_id=st.session_state["convo_id"],
        query_text=prompt,
        category=category,
        user_label=None
    )
    
    # Handle misspelling suggestions (simplified for now)
    # TODO: Implement enhanced misspelling detection
    
    # Respond to query
    respond_to_query(prompt, category)

# Auto-scroll
if st.session_state.get("scroll_flag"):
    st.write("\n" * 50)
    st.session_state["scroll_flag"] = False

# ===========================
# Footer
# ===========================
st.markdown("---")
st.markdown(
    "💡 **Need more help?** Try the national directories: "
    "[FindHelp.org](https://www.findhelp.org) | "
    "[211.org](https://www.211.org) | "
    "[HRSA Health Centers](https://findahealthcenter.hrsa.gov/)"
)


