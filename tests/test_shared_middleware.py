import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from shared.middleware import SetUserIdFromHeaderMiddleware
from shared.auth import TOKENS

def test_middleware_401_on_mcp_endpoint():
    app = Starlette()
    app.add_middleware(SetUserIdFromHeaderMiddleware)
    
    @app.route("/mcp")
    async def mcp_endpoint(request):
        return JSONResponse({"status": "ok"})
    
    client = TestClient(app)
    response = client.get("/mcp")
    
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["oauth_required"] is True

def test_middleware_success_with_token():
    app = Starlette()
    app.add_middleware(SetUserIdFromHeaderMiddleware)
    
    @app.route("/mcp")
    async def mcp_endpoint(request):
        from shared.storage import get_current_user
        return JSONResponse({"user_id": get_current_user()})
    
    # Mock a token
    token = "valid_token"
    user_id = "user_123"
    TOKENS[token] = user_id
    
    client = TestClient(app)
    response = client.get("/mcp", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    assert response.json()["user_id"] == user_id

