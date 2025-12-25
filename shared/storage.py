import os
import sqlite3
import json
from pathlib import Path
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime

# Storage configuration
STORAGE_ROOT_DEFAULT = "/tmp/librechat-mcp-storage" if os.name != 'nt' else "./storage"
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", STORAGE_ROOT_DEFAULT))
DB_PATH = STORAGE_ROOT / "mcp_tokens.db"

# User context using contextvars for thread-safe per-request storage
_user_id_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)

def set_current_user(user_id: Optional[str]):
    """Set the current user context for operations (thread-safe)"""
    _user_id_context.set(user_id)

def get_current_user() -> str:
    """Get the current user ID or raise error if not authenticated"""
    user_id = _user_id_context.get()
    if not user_id:
        raise ValueError("No user context set. User must be authenticated via OAuth.")

    # Reject placeholder strings (LibreChat bug: placeholders not replaced)
    if isinstance(user_id, str) and user_id.startswith("{{") and user_id.endswith("}}"):
        raise ValueError(
            f"Invalid user_id: '{user_id}' appears to be an unreplaced placeholder. "
            "This indicates LibreChat's processMCPEnv() didn't receive the user object."
        )

    return user_id

class TokenStore:
    """Persistent storage for user JWT tokens and cookies using SQLite"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_tokens (
                    user_id TEXT PRIMARY KEY,
                    jwt_token TEXT,
                    cookies TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_access_tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_token(self, user_id: str, jwt_token: str, cookies: Dict[str, str]):
        """Save or update a user's token and cookies (LibreChat JWT)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_tokens (user_id, jwt_token, cookies, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, jwt_token, json.dumps(cookies)))
            conn.commit()

    def get_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user's token and cookies (LibreChat JWT)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT jwt_token, cookies FROM user_tokens WHERE user_id = ?", 
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "jwt_token": row[0],
                    "cookies": json.loads(row[1])
                }
        return None

    def save_mcp_token(self, token: str, user_id: str):
        """Save or update an MCP access token"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mcp_access_tokens (token, user_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (token, user_id))
            conn.commit()

    def get_user_by_mcp_token(self, token: str) -> Optional[str]:
        """Retrieve a user_id associated with an MCP access token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT user_id FROM mcp_access_tokens WHERE token = ?", 
                (token,)
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def delete_token(self, user_id: str):
        """Delete a user's token"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM mcp_access_tokens WHERE user_id = ?", (user_id,))
            conn.commit()

# Singleton instance
token_store = TokenStore()

