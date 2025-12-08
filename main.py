import os
from fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Mount
from auth import routes as auth_routes

from tools.agent import (
    create_agent,
    list_agents,
    get_agent,
    update_agent,
    delete_agent,
    list_agent_categories,
    list_agent_tools,
)
from tools.model_context_protocol import (
    get_model_context_protocol_tools, get_model_context_protocol_info, get_model_context_protocol_status)
from tools.models import get_models
from tools.file_storage import (
    upload_file,
    create_note,
    list_files,
    read_file,
    modify_file,
    delete_file,
    search_files,
    set_current_user,
)
from tools.obsidian_sync import (
    configure_obsidian_sync,
    auto_configure_obsidian_sync,
    get_obsidian_sync_status,
    reset_obsidian_sync_failures,
)
from auth import get_user_from_token

libre_chat_mcp = FastMCP("LibreChat MCP Server", stateless_http=True)

# Register all tools
libre_chat_mcp.tool(create_agent)
libre_chat_mcp.tool(list_agents)
libre_chat_mcp.tool(get_agent)
libre_chat_mcp.tool(update_agent)
libre_chat_mcp.tool(delete_agent)
libre_chat_mcp.tool(list_agent_categories)
libre_chat_mcp.tool(list_agent_tools)
libre_chat_mcp.tool(get_model_context_protocol_tools)
libre_chat_mcp.tool(get_model_context_protocol_status)
libre_chat_mcp.tool(get_model_context_protocol_info)
libre_chat_mcp.tool(get_models)
libre_chat_mcp.tool(upload_file)
libre_chat_mcp.tool(create_note)
libre_chat_mcp.tool(list_files)
libre_chat_mcp.tool(read_file)
libre_chat_mcp.tool(modify_file)
libre_chat_mcp.tool(delete_file)
libre_chat_mcp.tool(search_files)
libre_chat_mcp.tool(configure_obsidian_sync)
libre_chat_mcp.tool(get_obsidian_sync_status)
libre_chat_mcp.tool(reset_obsidian_sync_failures)


class SetUserIdFromHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Rate limiting: track last write time per user (in-memory cache)
        self._last_config_write = {}
        self._write_cooldown = 30  # seconds
    
    async def dispatch(self, request: Request, call_next):
        import logging
        import time
        import json
        logger = logging.getLogger(__name__)
        
        user_id = None
        
        # Method 1: OAuth Token Extraction (HIGHEST PRIORITY)
        # Extract Bearer token from Authorization header
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header:
            try:
                # Check if it's a Bearer token
                if auth_header.startswith("Bearer ") or auth_header.startswith("bearer "):
                    token = auth_header.split(" ", 1)[1].strip()
                    user_id = get_user_from_token(token)
                    if user_id:
                        logger.info(f"✅ Extracted user_id from OAuth token: {user_id}")
                    else:
                        logger.debug(f"OAuth token provided but not found in token store: {token[:10]}...")
            except Exception as e:
                logger.debug(f"Could not extract user_id from OAuth token: {e}")
        
        # Method 2: Header-based extraction (if OAuth didn't work)
        if not user_id:
            user_id = request.headers.get("x-user-id")
        
        # Debug: Log URL and query params (only if user_id extraction fails)
        # These will be logged in the warning section below if needed
        
        # If header is missing or is the literal placeholder, try alternative extraction methods
        if not user_id or user_id == "{{LIBRECHAT_USER_ID}}":
            # Method 3: Try URL query parameter (fallback - testing if LibreChat replaces URL placeholders)
            # Also try parsing from raw query string
            query_user_id = request.query_params.get("userId") or request.query_params.get("user_id")
            
            # Fallback: Parse from raw query string if query_params doesn't work
            if not query_user_id and request.url.query:
                from urllib.parse import parse_qs
                parsed_query = parse_qs(request.url.query)
                query_user_id = parsed_query.get("userId", [None])[0] or parsed_query.get("user_id", [None])[0]
            
            if query_user_id and query_user_id != "{{LIBRECHAT_USER_ID}}":
                user_id = query_user_id
                logger.info(f"✅ Extracted user_id from URL query parameter: {user_id}")
                logger.info(f"   Full URL: {request.url}")
                logger.info(f"   Query params: {dict(request.query_params)}")
            else:
                logger.debug(f"Query parameter 'userId' not found or is placeholder. Raw query: '{request.url.query}', Parsed: {dict(request.query_params)}")
            
            # Method 4: Try to extract user ID from request body (MCP tool calls might include it)
            if not user_id:
                try:
                    # Read body (need to store it since we can only read it once)
                    body_bytes = await request.body()
                    if body_bytes:
                        body_data = json.loads(body_bytes)
                        # Check if there's a user ID in the params or metadata
                        if isinstance(body_data, dict):
                            params = body_data.get("params", {})
                            # Some MCP implementations might pass user context in params
                            if isinstance(params, dict):
                                user_id = params.get("userId") or params.get("user_id") or params.get("user")
                                if user_id:
                                    logger.info(f"Extracted user_id from request body: {user_id}")
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.debug(f"Could not extract user_id from request body: {e}")
            
            # If still no user_id, log warning with all headers for debugging
            if not user_id or user_id == "{{LIBRECHAT_USER_ID}}":
                logger.warning(f"User ID extraction failed. Tried: OAuth token, X-User-ID header, URL query parameter, request body")
                logger.warning(f"Final user_id value: {user_id}")
                logger.warning("This usually means LibreChat didn't pass the user object to processMCPEnv")
                logger.warning(f"URL: {request.url}")
                logger.warning(f"Query params: {dict(request.query_params)}")
                logger.warning(f"Authorization header present: {bool(auth_header)}")
                logger.debug("All headers received: " + str(dict(request.headers)))  # Use debug level for full headers
                # This is a known issue - LibreChat should be setting this header but isn't
                # The user object needs to be passed to processMCPEnv for the placeholder to be replaced
                # Set to None to prevent using placeholder string as user_id
                user_id = None
        
        # Only set user_id if it's valid (not None and not a placeholder)
        if user_id and not (user_id.startswith("{{") and user_id.endswith("}}")):
            set_current_user(user_id)
        else:
            # Don't set invalid user_id - get_current_user() will raise proper error
            set_current_user(None)
            
            # If OAuth is required and no valid user_id found, return 401 to trigger OAuth flow
            # Only do this for MCP endpoint, not for OAuth endpoints themselves
            if request.url.path == "/mcp" or request.url.path.endswith("/mcp"):
                from starlette.responses import JSONResponse
                logger.warning("OAuth required but no valid token found. Returning 401 to trigger OAuth flow.")
                return JSONResponse(
                    {"error": "OAuth authentication required", "oauth_required": True},
                    status_code=401
                )
        
        # Extract Obsidian sync configuration from headers
        # Note: LibreChat normalizes headers to lowercase, so use lowercase keys
        obsidian_repo_url = request.headers.get("x-obsidian-repo-url")
        obsidian_token = request.headers.get("x-obsidian-token")
        obsidian_branch = request.headers.get("x-obsidian-branch", "main")
        
        # Auto-configure if all required values are present and non-empty
        # Only check if this looks like a tool call (not initialization ping)
        # Check if path ends with /mcp (MCP endpoint) or is the root path
        path = str(request.url.path)
        is_mcp_request = path.endswith('/mcp') or path == '/' or path.endswith('/mcp/')
        
        if (user_id and 
            obsidian_repo_url and obsidian_repo_url.strip() and
            obsidian_token and obsidian_token.strip() and
            is_mcp_request):  # Only on actual MCP requests
            
            # Rate limiting: only check/write config once per cooldown period per user
            last_write = self._last_config_write.get(user_id, 0)
            current_time = time.time()
            
            if current_time - last_write >= self._write_cooldown:
                try:
                    await auto_configure_obsidian_sync(
                        user_id=user_id,
                        repo_url=obsidian_repo_url.strip(),
                        token=obsidian_token.strip(),
                        branch=obsidian_branch.strip() if obsidian_branch else "main"
                    )
                    # Update last write time only on successful write
                    self._last_config_write[user_id] = current_time
                except Exception as e:
                    # Log error but don't fail the request
                    logger.warning(f"Failed to auto-configure Obsidian sync for user {user_id}: {e}", exc_info=True)
        
        response = await call_next(request)
        set_current_user(None)
        return response


# Create the base app first
base_app = libre_chat_mcp.http_app()

# Add OAuth routes to the base app
# FastMCP's http_app() returns a Starlette app, which has a routes attribute
if hasattr(base_app, 'routes'):
    # Extend the routes list with OAuth routes
    base_app.routes.extend(auth_routes)
    print(f"✅ OAuth routes added. Total routes: {len(base_app.routes)}")
    print(f"   OAuth routes: {[r.path for r in auth_routes]}")
else:
    # Fallback: create a new app with combined routes
    print("⚠️  base_app doesn't have routes attribute, using fallback")
    combined_routes = list(base_app.routes) if hasattr(base_app, 'routes') else []
    combined_routes.extend(auth_routes)
    base_app = Starlette(routes=combined_routes)

# Wrap with middleware
app = SetUserIdFromHeaderMiddleware(base_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting LibreChatMCP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
