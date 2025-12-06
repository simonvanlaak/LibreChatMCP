"""
Middleware for extracting user context from request headers
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from tools import file_storage
import auth

class UserContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user_id from OAuth 2.0 Bearer Token.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        user_id = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Resolve user from token
            user_id = auth.get_user_from_token(token)
        
        # Set user context (or None)
        file_storage.set_current_user(user_id)
        
        try:
            response = await call_next(request)
        finally:
            file_storage.set_current_user(None)
        
        return response
