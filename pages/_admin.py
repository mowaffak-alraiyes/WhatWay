#!/usr/bin/env python3
"""
Admin page for data refresh and management.
Accessible via Streamlit pages or sidebar navigation.
"""

import streamlit as st
import data_loader
from pathlib import Path
import json

st.set_page_config(page_title="Admin - Data Management", layout="wide")

st.title("🔧 Admin - Data Management")

# Password protection: require ADMIN_PASSWORD in secrets or env (no default).
import os

_expected = ""
try:
    _expected = (st.secrets.get("ADMIN_PASSWORD") or "").strip()
except Exception:
    _expected = ""
if not _expected:
    _expected = (os.environ.get("ADMIN_PASSWORD") or "").strip()

if not _expected:
    st.error("Admin is locked: set ADMIN_PASSWORD in .streamlit/secrets.toml or .env")
    st.stop()

if "admin_authenticated" not in st.session_state:
    admin_password = st.text_input("Enter admin password:", type="password")
    if admin_password and admin_password == _expected:
        st.session_state["admin_authenticated"] = True
        st.rerun()
    elif admin_password:
        st.error("❌ Incorrect password")
    st.stop()

st.success("✅ Admin access granted")

# ===========================
# Data Refresh Section
# ===========================
st.header("📊 Data Refresh")

categories = ["Healthcare", "Education", "Resettlement / Legal / Shelter"]

col1, col2, col3 = st.columns(3)

for i, category in enumerate(categories):
    with [col1, col2, col3][i]:
        st.subheader(category)
        
        # Check if JSON file exists
        category_key = category.lower().replace(" / ", "_").replace(" ", "_")
        json_path = Path("data") / f"{category_key}.json"
        
        if json_path.exists():
            file_size = json_path.stat().st_size / 1024  # KB
            st.metric("File Size", f"{file_size:.1f} KB")
            
            # Count items
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    items = json.load(f)
                    st.metric("Items", len(items))
            except:
                st.metric("Items", "Error")
        else:
            st.warning("No JSON file found")
        
        # Refresh button
        if st.button(f"🔄 Refresh {category}", key=f"refresh_{category}"):
            with st.spinner(f"Refreshing {category} data..."):
                try:
                    # Clear cache
                    data_loader.load_category_data.clear()
                    
                    # Force refresh
                    data_loader.refresh_category_cache(category)
                    
                    # Reload
                    items = data_loader.load_category_data(category)
                    
                    st.success(f"✅ {category} refreshed! {len(items)} items loaded.")
                except Exception as e:
                    st.error(f"❌ Error refreshing {category}: {e}")

st.markdown("---")

# ===========================
# Data Validation Section
# ===========================
st.header("✔️ Data Validation")

if st.button("🔍 Validate All Data"):
    with st.spinner("Validating data..."):
        issues = []
        
        for category in categories:
            try:
                items = data_loader.load_category_data(category)
                
                for item in items:
                    # Check required fields
                    if not item.get("name"):
                        issues.append(f"{category}: Item {item.get('id')} missing name")
                    if not item.get("address"):
                        issues.append(f"{category}: {item.get('name')} missing address")
                    
                    # Check data types
                    if not isinstance(item.get("services", []), list):
                        issues.append(f"{category}: {item.get('name')} services not a list")
                    if not isinstance(item.get("languages", []), list):
                        issues.append(f"{category}: {item.get('name')} languages not a list")
                
                st.success(f"✅ {category}: {len(items)} items validated")
                
            except Exception as e:
                issues.append(f"{category}: Error - {e}")
        
        if issues:
            st.error(f"❌ Found {len(issues)} issues:")
            for issue in issues[:20]:  # Show first 20
                st.text(f"  • {issue}")
        else:
            st.success("✅ All data validated successfully!")

st.markdown("---")

# ===========================
# Data Statistics
# ===========================
st.header("📈 Data Statistics")

if st.button("📊 Show Statistics"):
    stats_data = []
    
    for category in categories:
        try:
            items = data_loader.load_category_data(category)
            
            # Count services
            all_services = set()
            all_languages = set()
            all_zips = set()
            with_badges = 0
            
            for item in items:
                all_services.update(item.get("services", []))
                all_languages.update(item.get("languages", []))
                if item.get("zip_code"):
                    all_zips.add(item["zip_code"])
                if item.get("availability_badges"):
                    with_badges += 1
            
            stats_data.append({
                "Category": category,
                "Total Items": len(items),
                "Unique Services": len(all_services),
                "Unique Languages": len(all_languages),
                "Unique ZIPs": len(all_zips),
                "With Badges": with_badges
            })
        except Exception as e:
            stats_data.append({
                "Category": category,
                "Error": str(e)
            })
    
    st.dataframe(stats_data, use_container_width=True)

st.markdown("---")

# ===========================
# Cache Management
# ===========================
st.header("🗑️ Cache Management")

if st.button("🗑️ Clear All Caches"):
    try:
        data_loader.load_category_data.clear()
        st.success("✅ All caches cleared!")
    except Exception as e:
        st.error(f"❌ Error clearing cache: {e}")

