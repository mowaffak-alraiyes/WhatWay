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

class NeonDatabase:
    def __init__(self):
        self.connection = None
        self.pool = None
        
    def get_connection(self):
        """Get database connection using passwordless token"""
        try:
            if self.connection is None or self.connection.closed:
                # Try to get credentials from Streamlit secrets first, then environment variables, then fallback
                try:
                    # Use Streamlit secrets
                    host = st.secrets["NEON_DB_HOST"]
                    dbname = st.secrets["NEON_DB_NAME"]
                    user = st.secrets["NEON_DB_USER"]
                    token = st.secrets["NEON_PASSWORDLESS_TOKEN"]
                    sslmode = st.secrets["NEON_SSLMODE"]
                    logger.info("Using Streamlit secrets for database connection")
                except (KeyError, AttributeError):
                    # Fallback to environment variables
                    host = os.getenv("NEON_DB_HOST", "YOUR_NEON_DB_HOST")
                    dbname = os.getenv("NEON_DB_NAME", "YOUR_NEON_DB_NAME")
                    user = os.getenv("NEON_DB_USER", "YOUR_NEON_DB_USER")
                    token = os.getenv("NEON_PASSWORDLESS_TOKEN", "YOUR_NEON_PASSWORDLESS_TOKEN")
                    sslmode = os.getenv("NEON_SSLMODE", "require")
                    logger.info("Using environment variables for database connection")
                
                if not token:
                    logger.error("NEON_PASSWORDLESS_TOKEN not found in secrets or environment")
                    return None
                
                logger.info(f"Connecting to database: {host}/{dbname} as {user}")
                
                # Use passwordless token as password
                conn_str = f"postgresql://{user}:{token}@{host}/{dbname}?sslmode={sslmode}"
                
                self.connection = psycopg.connect(conn_str, row_factory=dict_row)
                logger.info("Connected to Neon database")
            
            return self.connection
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
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

