import os
import json
import logging
from typing import Optional, Dict, Any
import psycopg
from psycopg.rows import dict_row
import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DATABASE_KEYS = (
    "NEON_DB_HOST",
    "NEON_DB_NAME",
    "NEON_DB_USER",
    "NEON_PASSWORDLESS_TOKEN",
)


def _usable_setting(value: Any) -> bool:
    """Return whether a setting contains a real value rather than a template."""
    text = str(value or "").strip()
    return bool(text) and not text.upper().startswith("YOUR_")


def _database_config() -> Optional[Dict[str, str]]:
    """Load a complete database config without requiring Streamlit secrets.

    Environment variables are preferred for containers and local development.
    Streamlit secrets remain supported for existing hosted deployments. Missing
    configuration is a valid browser-only mode, not a connection error.
    """
    environment = {key: os.getenv(key, "") for key in _DATABASE_KEYS}
    if all(_usable_setting(value) for value in environment.values()):
        return {
            **environment,
            "NEON_SSLMODE": os.getenv("NEON_SSLMODE", "require"),
        }

    try:
        secrets_config = {key: st.secrets.get(key, "") for key in _DATABASE_KEYS}
        sslmode = st.secrets.get("NEON_SSLMODE", "require")
    except Exception:
        return None

    if not all(_usable_setting(value) for value in secrets_config.values()):
        return None
    return {**secrets_config, "NEON_SSLMODE": sslmode or "require"}

class NeonDatabase:
    def __init__(self):
        self.connection = None
        self.pool = None
        self._connection_attempted = False
        self.unavailable_reason = None
        
    def get_connection(self):
        """Get database connection using passwordless token"""
        if self.connection is not None and not self.connection.closed:
            return self.connection
        if self._connection_attempted:
            return None

        config = _database_config()
        if config is None:
            self._connection_attempted = True
            self.unavailable_reason = "not_configured"
            logger.info("Database not configured; continuing in browser-only mode")
            return None

        self._connection_attempted = True
        try:
            self.connection = psycopg.connect(
                host=config["NEON_DB_HOST"],
                dbname=config["NEON_DB_NAME"],
                user=config["NEON_DB_USER"],
                password=config["NEON_PASSWORDLESS_TOKEN"],
                sslmode=config["NEON_SSLMODE"],
                row_factory=dict_row,
            )
            self.unavailable_reason = None
            logger.info("Connected to configured database")
            return self.connection
        except Exception as e:
            self.unavailable_reason = "connection_failed"
            logger.warning("Configured database is currently unavailable: %s", e)
            return None
    
    def initialize_database(self):
        """Initialize database tables if they don't exist"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cur:
                # Create conversations table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        convo_id VARCHAR(50) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create user_messages table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_messages (
                        id SERIAL PRIMARY KEY,
                        convo_id VARCHAR(50) NOT NULL,
                        query_text TEXT NOT NULL,
                        category VARCHAR(100),
                        user_label VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (convo_id) REFERENCES conversations(convo_id)
                    )
                """)
                
                # Create assistant_messages table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS assistant_messages (
                        id SERIAL PRIMARY KEY,
                        convo_id VARCHAR(50) NOT NULL,
                        reply_text TEXT NOT NULL,
                        reply_json JSONB,
                        category VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (convo_id) REFERENCES conversations(convo_id)
                    )
                """)
                
                # ===========================
                # User Authentication Tables
                # ===========================
                
                # Create users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        password_salt VARCHAR(255) NOT NULL,
                        display_name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                
                # ===========================
                # Comments/Discussion Tables
                # ===========================
                
                # Create comments table (supports threaded replies)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS comments (
                        id SERIAL PRIMARY KEY,
                        resource_id VARCHAR(50) NOT NULL,
                        resource_category VARCHAR(100) NOT NULL,
                        user_id INTEGER NOT NULL,
                        parent_id INTEGER,
                        content TEXT NOT NULL,
                        rating SMALLINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_deleted BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (parent_id) REFERENCES comments(id)
                    )
                """)
                # Migrate older DBs that lack rating
                cur.execute("""
                    ALTER TABLE comments
                    ADD COLUMN IF NOT EXISTS rating SMALLINT
                """)
                
                # Create comment_votes table (for upvotes/downvotes)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS comment_votes (
                        id SERIAL PRIMARY KEY,
                        comment_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        vote_type INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (comment_id) REFERENCES comments(id),
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        UNIQUE(comment_id, user_id)
                    )
                """)
                
                # Create indexes for better query performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_comments_resource 
                    ON comments(resource_id, resource_category)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_comments_parent 
                    ON comments(parent_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_comment_votes_comment 
                    ON comment_votes(comment_id)
                """)
                
                conn.commit()
                logger.info("Database tables initialized successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    def save_user_message(self, convo_id: str, query_text: str, category: str, user_label: Optional[str] = None):
        """Save user message to database"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cur:
                # Ensure conversation exists
                cur.execute("""
                    INSERT INTO conversations (convo_id) 
                    VALUES (%s) 
                    ON CONFLICT (convo_id) DO NOTHING
                """, (convo_id,))
                
                # Insert user message
                cur.execute("""
                    INSERT INTO user_messages (convo_id, query_text, category, user_label)
                    VALUES (%s, %s, %s, %s)
                """, (convo_id, query_text, category, user_label))
                
                conn.commit()
                logger.info(f"Saved user message for conversation {convo_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
            return False
    
    def save_assistant_message(self, convo_id: str, reply_text: str, reply_json: Dict[str, Any], category: str):
        """Save assistant message to database"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            with conn.cursor() as cur:
                # Ensure conversation exists
                cur.execute("""
                    INSERT INTO conversations (convo_id) 
                    VALUES (%s) 
                    ON CONFLICT (convo_id) DO NOTHING
                """, (convo_id,))
                
                # Insert assistant message
                cur.execute("""
                    INSERT INTO assistant_messages (convo_id, reply_text, reply_json, category)
                    VALUES (%s, %s, %s, %s)
                """, (convo_id, reply_text, json.dumps(reply_json), category))
                
                conn.commit()
                logger.info(f"Saved assistant message for conversation {convo_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")
            return False
    
    def get_conversation_history(self, convo_id: str) -> list:
        """Get conversation history for a given conversation ID"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
                
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        'user' as type,
                        query_text as text,
                        category,
                        created_at
                    FROM user_messages 
                    WHERE convo_id = %s
                    UNION ALL
                    SELECT 
                        'assistant' as type,
                        reply_text as text,
                        category,
                        created_at
                    FROM assistant_messages 
                    WHERE convo_id = %s
                    ORDER BY created_at ASC
                """, (convo_id, convo_id))
                
                return cur.fetchall()
                
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Database connection closed")

# Global database instance (lazy initialization)
db = None

def get_db_instance():
    """Get or create database instance"""
    global db
    if db is None:
        db = NeonDatabase()
    return db

# Convenience functions
def initialize_database():
    """Initialize the database tables"""
    return get_db_instance().initialize_database()

def save_user_message(convo_id: str, query_text: str, category: str, user_label: Optional[str] = None):
    """Save a user message"""
    return get_db_instance().save_user_message(convo_id, query_text, category, user_label)

def save_assistant_message(convo_id: str, reply_text: str, reply_json: Dict[str, Any], category: str):
    """Save an assistant message"""
    return get_db_instance().save_assistant_message(convo_id, reply_text, reply_json, category)

def get_conversation_history(convo_id: str) -> list:
    """Get conversation history"""
    return get_db_instance().get_conversation_history(convo_id)

def close_database():
    """Close the database connection"""
    if db is not None:
        db.close()
