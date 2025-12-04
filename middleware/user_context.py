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
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract user_id from headers
        user_id = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
        
        if user_id:
            # Set user context for file storage operations
            file_storage.set_current_user(user_id)
        
        # Process the request
        response = await call_next(request)
        
        # Clear user context after request
        file_storage._current_user_id = None
        
        return response
