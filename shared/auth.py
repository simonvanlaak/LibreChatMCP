import os
import secrets
import json
import requests
import logging
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_200_OK
from .storage import token_store

logger = logging.getLogger(__name__)

# LibreChat API configuration
API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")

# OAuth client configuration
# In-memory storage for auth codes (transient)
AUTH_CODES = {}  # code -> user_id
# In-memory storage for MCP access tokens
# Note: These are the tokens used by LibreChat to call this MCP server
TOKENS = {}      # token -> user_id

def generate_token():
    return secrets.token_urlsafe(32)

def generate_auth_code():
    return secrets.token_urlsafe(16)

async def authorize(request: Request):
    """
    OAuth 2.0 Authorization Endpoint
    Renders a login form and verifies credentials against LibreChat API.
    """
    params = request.query_params
    redirect_uri = params.get("redirect_uri")
    state = params.get("state")
    client_id = params.get("client_id")

    if not redirect_uri or not state:
        return HTMLResponse("Missing redirect_uri or state", status_code=400)

    # Extract user_id from state (format: userId:serverName)
    try:
        user_id = state.split(":")[0]
    except Exception:
        return HTMLResponse("Invalid state parameter format. Expected userId:serverName", status_code=400)

    # Handle Login Form Submission
    if request.method == "POST":
        form = await request.form()
        action = form.get("action")
        
        if action == "login":
            email = form.get("email")
            password = form.get("password")
            
            if not email or not password:
                return _render_login_page(user_id, error="Email and password are required")
            
            # Verify credentials with LibreChat API
            try:
                session = requests.Session()
                login_url = f"{API_BASE_URL}/auth/login"
                resp = session.post(login_url, json={"email": email, "password": password}, timeout=10)
                
                if resp.status_code != 200:
                    logger.warning(f"Login failed for {email}: {resp.text}")
                    return _render_login_page(user_id, error="Invalid credentials or login failed")
                
                data = resp.json()
                if data.get("twoFAPending"):
                    return _render_login_page(user_id, error="2FA is enabled. Please disable 2FA for MCP access.")
                
                jwt_token = data.get("token")
                if not jwt_token:
                    return _render_login_page(user_id, error="No token received from LibreChat")
                
                # Extract cookies
                cookies = {c.name: c.value for c in session.cookies}
                
                # Save to persistent storage
                token_store.save_token(user_id, jwt_token, cookies)
                
                # Generate auth code for OAuth flow
                code = generate_auth_code()
                AUTH_CODES[code] = user_id
                
                # Redirect back to LibreChat
                sep = "&" if "?" in redirect_uri else "?"
                target = f"{redirect_uri}{sep}code={code}&state={state}"
                return RedirectResponse(target, status_code=302)
                
            except Exception as e:
                logger.error(f"Error during login proxy: {e}")
                return _render_login_page(user_id, error=f"Internal error: {str(e)}")

    # Render login page
    return _render_login_page(user_id)

def _render_login_page(user_id: str, error: str = None):
    error_html = f'<p style="color: red;">{error}</p>' if error else ""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login to LibreChat MCP</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }}
            .card {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 350px; text-align: center; }}
            h2 {{ margin-top: 0; color: #333; }}
            p {{ color: #666; font-size: 0.9rem; }}
            .form-group {{ margin-bottom: 1rem; text-align: left; }}
            label {{ display: block; margin-bottom: 0.5rem; color: #555; }}
            input {{ width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
            .btn {{ display: block; width: 100%; padding: 0.75rem; border: none; border-radius: 4px; background: #007bff; color: white; font-size: 1rem; cursor: pointer; margin-top: 1rem; }}
            .btn:hover {{ background: #0056b3; }}
            .user-id {{ background: #eee; padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Connect LibreChat MCP</h2>
            <p>Please log in with your LibreChat credentials to grant access to this MCP server.</p>
            <p>User ID: <span class="user-id">{user_id}</span></p>
            {error_html}
            <form method="POST">
                <input type="hidden" name="action" value="login">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" name="email" required autofocus>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn">Login & Connect</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def token(request: Request):
    """
    OAuth 2.0 Token Endpoint
    Exchanges authorization code for an MCP access token.
    """
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()
        
        code = data.get("code")
        if not code or code not in AUTH_CODES:
            return JSONResponse({"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}, status_code=400)
            
        user_id = AUTH_CODES.pop(code)
        access_token = generate_token()
        TOKENS[access_token] = user_id
        
        logger.info(f"MCP access token generated for user_id: {user_id}")
        
        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600 * 24 * 30, # 30 days
            "scope": "librechat_mcp"
        })
    
    return JSONResponse({"error": "method_not_allowed"}, status_code=405)

def get_user_from_token(token: str):
    """Get the user_id associated with an MCP access token"""
    return TOKENS.get(token)

routes = [
    Route("/authorize", authorize, methods=["GET", "POST"]),
    Route("/token", token, methods=["POST"]),
]

