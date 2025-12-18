"""
Middleware for LibreChatMCP.
Handles OAuth token extraction and user identification.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from .auth import get_user_from_token
from .storage import set_current_user

logger = logging.getLogger(__name__)

class SetUserIdFromHeaderMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user ID from OAuth token or headers.
    """
    
    async def dispatch(self, request: Request, call_next):
        user_id = None
        
        # 1. OAuth Token Extraction (Bearer token)
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if auth_header:
            try:
                if auth_header.lower().startswith("bearer "):
                    token = auth_header.split(" ", 1)[1].strip()
                    user_id = get_user_from_token(token)
                    if user_id:
                        logger.info(f"Extracted user_id from OAuth token: {user_id}")
            except Exception as e:
                logger.warning(f"Could not extract user_id from OAuth token: {e}")
        
        # 2. Direct Header Extraction (Fallback for non-OAuth requests if allowed)
        if not user_id:
            user_id = request.headers.get("x-user-id")
        
        # 3. URL Query Parameter (Fallback)
        if not user_id or user_id.startswith("{{"):
            query_user_id = request.query_params.get("userId") or request.query_params.get("user_id")
            if query_user_id and not query_user_id.startswith("{{"):
                user_id = query_user_id

        # Validate and set user context
        if user_id and not user_id.startswith("{{"):
            set_current_user(user_id)
        else:
            set_current_user(None)
            
            # If OAuth is required and no valid user_id found, return 401
            # Only trigger for /mcp endpoint
            if request.url.path == "/mcp" or request.url.path.endswith("/mcp"):
                logger.warning("OAuth required but no valid token found. Returning 401.")
                response = JSONResponse(
                    {"error": "OAuth authentication required", "oauth_required": True},
                    status_code=401
                )
                response.headers["WWW-Authenticate"] = "Bearer"
                return response
        
        response = await call_next(request)
        set_current_user(None)
        return response

