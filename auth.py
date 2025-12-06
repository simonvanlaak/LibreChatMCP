import os
import secrets
import json
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_200_OK

# In-memory storage for simplicity (since we are a single replica for now)
# In production with multiple replicas, this should be Redis
AUTH_CODES = {}  # code -> user_id
TOKENS = {}      # token -> user_id

def generate_token():
    return secrets.token_urlsafe(32)

def generate_auth_code():
    return secrets.token_urlsafe(16)

async def authorize(request: Request):
    """
    OAuth 2.0 Authorization Endpoint
    """
    params = request.query_params
    redirect_uri = params.get("redirect_uri")
    state = params.get("state")
    client_id = params.get("client_id")

    if not redirect_uri or not state:
        return HTMLResponse("Missing redirect_uri or state", status_code=400)

    # Extract user_id from state (format: userId:serverName)
    # This is the critical step where we identify the user without manual input
    try:
        user_id_raw = state.split(":")[0]
        # Sanitize or validate if necessary
        user_id = user_id_raw
    except Exception:
        return HTMLResponse("Invalid state parameter format. Expected userId:serverName", status_code=400)

    # If we received a POST (user clicked "Connect"), generate code and redirect
    if request.method == "POST":
        form = await request.form()
        if form.get("action") == "approve":
            code = generate_auth_code()
            AUTH_CODES[code] = user_id
            
            # Redirect back to LibreChat
            # Separator is ? or & depending on if redirect_uri already has params
            sep = "&" if "?" in redirect_uri else "?"
            target = f"{redirect_uri}{sep}code={code}&state={state}"
            return RedirectResponse(target, status_code=302)
        else:
            return HTMLResponse("Access Denied", status_code=400)

    # Render simple confirmation page
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connect LibreChat Files</title>
        <style>
            body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; }}
            .card {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 300px; text-align: center; }}
            h2 {{ margin-top: 0; color: #333; }}
            p {{ color: #666; }}
            .btn {{ display: block; width: 100%; padding: 0.75rem; border: none; border-radius: 4px; background: #007bff; color: white; font-size: 1rem; cursor: pointer; }}
            .btn:hover {{ background: #0056b3; }}
            .user-id {{ background: #eee; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Connect Storage</h2>
            <p>LibreChat is requesting access to your personal file storage.</p>
            <p>User Context: <span class="user-id">{user_id}</span></p>
            <form method="POST">
                <input type="hidden" name="action" value="approve">
                <button type="submit" class="btn">Connect</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def token(request: Request):
    """
    OAuth 2.0 Token Endpoint
    """
    if request.method == "POST":
        # Can be form-encoded or JSON
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()
        
        code = data.get("code")
        # grant_type = data.get("grant_type") # Should be Authorization Code
        
        if not code or code not in AUTH_CODES:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
            
        user_id = AUTH_CODES.pop(code) # Consume code
        access_token = generate_token()
        TOKENS[access_token] = user_id
        
        return JSONResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600 * 24 * 30, # 30 days
            "scope": "file_storage"
        })
    
    return JSONResponse({"error": "method_not_allowed"}, status_code=405)

def get_user_from_token(token: str):
    return TOKENS.get(token)

routes = [
    Route("/authorize", authorize, methods=["GET", "POST"]),
    Route("/token", token, methods=["POST"]),
]
