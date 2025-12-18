import os
import requests
import logging
from typing import Optional, Dict
from shared.storage import get_current_user, token_store

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")

def get_jwt_token(force_refresh: bool = False) -> str:
    """
    Get the JWT token for the current user from the token store.
    If force_refresh is True, it will attempt to refresh the token using cookies.
    """
    user_id = get_current_user()
    token_data = token_store.get_token(user_id)
    
    if not token_data:
        raise RuntimeError(f"No token found for user {user_id}. User must authenticate via OAuth.")
    
    jwt_token = token_data.get("jwt_token")
    
    if force_refresh:
        logger.info(f"Forcing token refresh for user {user_id}")
        refreshed_token = refresh_jwt_token_with_cookies(user_id, token_data.get("cookies", {}))
        if refreshed_token:
            return refreshed_token

    return jwt_token

def auth_headers() -> dict:
    """Get Authorization header for the current user"""
    token = get_jwt_token()
    return {"Authorization": f"Bearer {token}"}

def default_headers() -> dict:
    """Get default headers including Authorization for the current user"""
    headers = auth_headers()
    headers["Accept"] = "application/json"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    return headers

def refresh_jwt_token_with_cookies(user_id: str, cookies: Dict[str, str]) -> Optional[str]:
    """
    Refresh JWT token using stored cookies for a specific user.
    """
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value)
    
    refresh_url = f"{API_BASE_URL}/auth/refresh"
    try:
        resp = session.post(refresh_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "token" in data:
            new_jwt = data["token"]
            new_cookies = {c.name: c.value for c in session.cookies}
            token_store.save_token(user_id, new_jwt, new_cookies)
            logger.info(f"Successfully refreshed JWT for user {user_id}")
            return new_jwt
    except Exception as e:
        logger.error(f"JWT refresh failed for user {user_id}: {e}")
    return None

def resilient_request(method, url, **kwargs):
    """Make a request, refresh JWT if expired, and retry once."""
    user_id = get_current_user()
    
    logger.debug(f"Request: {method.upper()} {url}")
    resp = requests.request(method, url, **kwargs)
    
    if resp.status_code == 401:
        logger.info(f"JWT expired for user {user_id}, attempting refresh...")
        token_data = token_store.get_token(user_id)
        if token_data:
            new_token = refresh_jwt_token_with_cookies(user_id, token_data.get("cookies", {}))
            if new_token:
                headers = kwargs.get("headers", {})
                headers["Authorization"] = f"Bearer {new_token}"
                kwargs["headers"] = headers
                logger.debug(f"Retry request: {method.upper()} {url}")
                resp = requests.request(method, url, **kwargs)
    
    return resp
