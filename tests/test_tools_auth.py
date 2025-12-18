import pytest
import os
import sys
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.storage import set_current_user, token_store
# We import tools.auth inside the test to allow patching if needed, 
# but for now we expect it to fail based on current implementation.

def test_default_headers_with_user_token(tmp_path):
    from tools.auth import default_headers
    
    # Set up temp db
    db_path = tmp_path / "test_auth_tools.db"
    # Note: We need to ensure token_store uses this path
    token_store.db_path = db_path
    token_store._init_db()
    
    user_id = "test_user_auth"
    jwt = "user_specific_jwt_123"
    token_store.save_token(user_id, jwt, {})
    
    set_current_user(user_id)
    try:
        headers = default_headers()
        assert headers["Authorization"] == f"Bearer {jwt}"
    finally:
        set_current_user(None)

def test_default_headers_fails_without_user():
    from tools.auth import default_headers
    set_current_user(None)
    with pytest.raises(ValueError, match="No user context set"):
        default_headers()

