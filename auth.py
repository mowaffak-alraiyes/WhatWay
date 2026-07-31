#!/usr/bin/env python3
"""
Authentication module for user management.
Provides login, registration, and session management functionality.
Designed to be modular and extensible for future OAuth integration.
"""

import streamlit as st
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import database as db

logger = logging.getLogger(__name__)

# ===========================
# Password Hashing
# ===========================

def hash_password(password: str, salt: str = None) -> tuple:
    """
    Hash a password with a salt using SHA-256.
    Returns (hashed_password, salt) tuple.
    """
    if salt is None:
        salt = secrets.token_hex(32)
    
    # Combine password and salt, then hash
    salted = f"{password}{salt}"
    hashed = hashlib.sha256(salted.encode()).hexdigest()
    
    return hashed, salt

def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """Verify a password against its hash."""
    computed_hash, _ = hash_password(password, salt)
    return computed_hash == hashed_password

# ===========================
# Session Management
# ===========================

def init_session_state():
    """Initialize authentication-related session state."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "auth_message" not in st.session_state:
        st.session_state["auth_message"] = None

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the currently logged-in user, or None if not authenticated."""
    init_session_state()
    if st.session_state.get("authenticated"):
        return st.session_state.get("user")
    return None

def is_authenticated() -> bool:
    """Check if user is currently authenticated."""
    init_session_state()
    return st.session_state.get("authenticated", False)

def login_user(user_data: Dict[str, Any]):
    """Set the user as logged in."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = user_data
    st.session_state["auth_message"] = None

def logout_user():
    """Log out the current user."""
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["auth_message"] = "You have been logged out."

# ===========================
# Database Operations
# ===========================

def create_user(username: str, email: str, password: str, display_name: str = None) -> tuple:
    """
    Create a new user account.
    Returns (success: bool, message: str, user_id: int or None)
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return False, "Database connection failed", None
        
        with conn.cursor() as cur:
            # Check if username already exists
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                return False, "Username already exists", None
            
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return False, "Email already registered", None
            
            # Hash password
            hashed_password, salt = hash_password(password)
            
            # Set display name to username if not provided
            if not display_name:
                display_name = username
            
            # Insert new user
            cur.execute("""
                INSERT INTO users (username, email, password_hash, password_salt, display_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (username, email, hashed_password, salt, display_name))
            
            user_id = cur.fetchone()["id"]
            conn.commit()
            
            logger.info(f"Created new user: {username} (ID: {user_id})")
            return True, "Account created successfully!", user_id
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False, f"Error creating account: {str(e)}", None

def authenticate_user(username: str, password: str) -> tuple:
    """
    Authenticate a user with username/email and password.
    Returns (success: bool, message: str, user_data: dict or None)
    """
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return False, "Database connection failed", None
        
        with conn.cursor() as cur:
            # Find user by username or email
            cur.execute("""
                SELECT id, username, email, password_hash, password_salt, display_name, created_at
                FROM users 
                WHERE username = %s OR email = %s
            """, (username, username))
            
            user = cur.fetchone()
            
            if not user:
                return False, "Invalid username or password", None
            
            # Verify password
            if not verify_password(password, user["password_hash"], user["password_salt"]):
                return False, "Invalid username or password", None
            
            # Update last login
            cur.execute("""
                UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
            """, (user["id"],))
            conn.commit()
            
            # Return user data (without sensitive fields)
            user_data = {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "display_name": user["display_name"],
                "created_at": user["created_at"]
            }
            
            logger.info(f"User authenticated: {username}")
            return True, "Login successful!", user_data
            
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return False, f"Authentication error: {str(e)}", None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user data by ID."""
    try:
        conn = db.get_db_instance().get_connection()
        if not conn:
            return None
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, email, display_name, created_at
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cur.fetchone()
            return dict(user) if user else None
            
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        return None

# ===========================
# UI Components
# ===========================

def render_login_form():
    """Render the login form."""
    st.subheader("🔐 Login")
    
    with st.form("login_form"):
        username = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("Please fill in all fields")
            else:
                success, message, user_data = authenticate_user(username, password)
                if success:
                    login_user(user_data)
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

def render_register_form():
    """Render the registration form."""
    st.subheader("📝 Create Account")
    
    with st.form("register_form"):
        username = st.text_input("Username", help="Choose a unique username")
        email = st.text_input("Email")
        display_name = st.text_input("Display Name (optional)", help="How your name appears to others")
        password = st.text_input("Password", type="password")
        password_confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", use_container_width=True)
        
        if submitted:
            # Validation
            if not username or not email or not password:
                st.error("Please fill in all required fields")
            elif len(username) < 3:
                st.error("Username must be at least 3 characters")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif password != password_confirm:
                st.error("Passwords do not match")
            elif "@" not in email:
                st.error("Please enter a valid email address")
            else:
                success, message, user_id = create_user(username, email, password, display_name)
                if success:
                    st.success(message)
                    st.info("You can now log in with your credentials.")
                else:
                    st.error(message)

def render_auth_sidebar(lang: str = "en"):
    """Render authentication controls in the sidebar."""
    import core.i18n as i18n

    init_session_state()
    
    if is_authenticated():
        user = get_current_user()
        st.sidebar.markdown(f"👤 **{user.get('display_name', user.get('username'))}**")
        if st.sidebar.button(i18n.t("logout", lang), use_container_width=True):
            logout_user()
            st.rerun()
    else:
        auth_tab = st.sidebar.radio(
            i18n.t("auth", lang),
            ["login", "register"],
            format_func=lambda k: i18n.t(k, lang),
            horizontal=True,
            label_visibility="collapsed",
            key="auth_tab_radio",
        )
        
        if auth_tab == "login":
            render_login_form_sidebar(lang)
        else:
            render_register_form_sidebar(lang)

def render_login_form_sidebar(lang: str = "en"):
    """Compact login form for sidebar."""
    import core.i18n as i18n

    username = st.sidebar.text_input(i18n.t("username_email", lang), key="sidebar_login_user")
    password = st.sidebar.text_input(i18n.t("password", lang), type="password", key="sidebar_login_pass")
    
    if st.sidebar.button(i18n.t("login", lang), use_container_width=True, key="sidebar_login_btn"):
        if username and password:
            success, message, user_data = authenticate_user(username, password)
            if success:
                login_user(user_data)
                st.rerun()
            else:
                st.sidebar.error(message)
        else:
            st.sidebar.error(i18n.t("fill_fields", lang))

def render_register_form_sidebar(lang: str = "en"):
    """Compact registration form for sidebar."""
    import core.i18n as i18n

    st.sidebar.caption("Create an account to post reviews.")
    username = st.sidebar.text_input(i18n.t("username", lang), key="sidebar_reg_user")
    email = st.sidebar.text_input(i18n.t("email", lang), key="sidebar_reg_email")
    password = st.sidebar.text_input(
        i18n.t("password", lang), type="password", key="sidebar_reg_pass",
        help="At least 6 characters",
    )

    if st.sidebar.button(i18n.t("create_account", lang), use_container_width=True, key="sidebar_reg_btn"):
        if username and email and password:
            if len(password) < 6:
                st.sidebar.error(i18n.t("password_short", lang))
            else:
                success, message, _ = create_user(username, email, password)
                if success:
                    st.sidebar.success(i18n.t("account_created", lang))
                else:
                    st.sidebar.error(message)
        else:
            st.sidebar.error(i18n.t("fill_fields", lang))

def require_auth(func):
    """Decorator to require authentication for a function."""
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            st.warning("⚠️ Please log in to access this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper

