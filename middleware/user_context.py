"""
Middleware for extracting user context from request headers
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from tools import file_storage


class UserContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user_id from X-User-ID header and set user context.
    
    LibreChat sends the user_id via the X-User-ID header with value {{LIBRECHAT_USER_ID}}.
    This middleware extracts that value and makes it available to file storage tools.
    Uses contextvars for thread-safe per-request storage.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract user_id from headers
        user_id = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
        
        # Only set user context if we have a valid user ID
        # Ignore template strings like "{{LIBRECHAT_USER_ID}}" which are used during initialization
        if user_id and user_id != "{{LIBRECHAT_USER_ID}}" and not user_id.startswith("{{"):
            # Set user context for file storage operations (uses contextvars)
            file_storage.set_current_user(user_id)
        else:
            # No valid user context - this is OK for initialization and non-file-storage operations
            # File storage tools will raise an error if called without user context
            file_storage.set_current_user(None)
        
        try:
            # Process the request - allow it to proceed even without user context
            # This allows initialization to work without user context
            response = await call_next(request)
        finally:
            # Clear user context after request (contextvars automatically handle cleanup)
            # But we can explicitly clear it for safety
            file_storage.set_current_user(None)
        
        return response
