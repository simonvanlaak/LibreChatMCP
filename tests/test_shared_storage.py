import pytest
import sqlite3
import json
from pathlib import Path
import sys
import os

# Add the project root to sys.path to allow imports from LibreChatMCP
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.storage import TokenStore

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_mcp_tokens.db"
    return db_path

def test_token_store_init(temp_db):
    store = TokenStore(db_path=temp_db)
    assert temp_db.exists()
    
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_tokens'")
        assert cursor.fetchone() is not None

def test_save_and_get_token(temp_db):
    store = TokenStore(db_path=temp_db)
    user_id = "user_123"
    jwt = "test_jwt"
    cookies = {"session": "abc"}
    
    store.save_token(user_id, jwt, cookies)
    data = store.get_token(user_id)
    
    assert data["jwt_token"] == jwt
    assert data["cookies"] == cookies

def test_delete_token(temp_db):
    store = TokenStore(db_path=temp_db)
    user_id = "user_123"
    store.save_token(user_id, "jwt", {})
    
    store.delete_token(user_id)
    assert store.get_token(user_id) is None

