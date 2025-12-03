import os
import requests
from typing import Optional

API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")
_token_cache: Optional[str] = None
_cookies_path = os.path.join(os.path.dirname(__file__), "cookies.txt")

def get_jwt_token(force_refresh: bool = False) -> str:
    global _token_cache
    if _token_cache and not force_refresh:
        return _token_cache
    email = os.environ.get("LIBRECHAT_EMAIL")
    password = os.environ.get("LIBRECHAT_PASSWORD")
    if not email or not password:
        raise RuntimeError("LIBRECHAT_EMAIL and LIBRECHAT_PASSWORD must be set in environment.")
    login_url = f"{API_BASE_URL}/auth/login"
    session = requests.Session()
    resp = session.post(login_url, json={"email": email, "password": password})
    try:
        resp.raise_for_status()
    except Exception as e:
        print("[MCP] Login failed!")
        print("[MCP] Status code:", resp.status_code)
        print("[MCP] Response text:", resp.text)
        raise
    try:
        data = resp.json()
    except Exception as e:
        print("[MCP] Login response is not valid JSON!")
        print(f"[MCP] Status code: {resp.status_code}")
        print(f"[MCP] Response text: {resp.text}")
        raise
    if data.get("twoFAPending"):
        raise RuntimeError("2FA is enabled for this account. Automated login is not supported.")
    if "token" not in data:
        raise RuntimeError(f"No token in login response. Response: {data}")
    _token_cache = data["token"]
    os.environ["LIBRECHAT_JWT_TOKEN"] = _token_cache
    with open("../.librechat_token", "w") as f:
        f.write(_token_cache)
    with open(_cookies_path, "w") as f:
        for c in session.cookies:
            f.write(f"{c.name}\t{c.value}\n")
    return _token_cache

def auth_headers() -> dict:
    token = get_jwt_token()
    return {"Authorization": f"Bearer {token}"}

def default_headers() -> dict:
    headers = auth_headers()
    headers["Accept"] = "application/json"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    return headers

def load_cookies_to_session(session):
    if not os.path.exists(_cookies_path):
        return session
    with open(_cookies_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                session.cookies.set(parts[0], parts[1])
    return session

def refresh_jwt_token_with_cookies() -> Optional[str]:
    global _token_cache
    session = requests.Session()
    session = load_cookies_to_session(session)
    refresh_url = f"{API_BASE_URL}/auth/refresh"
    try:
        resp = session.post(refresh_url)
        resp.raise_for_status()
        data = resp.json()
        if "token" in data:
            _token_cache = data["token"]
            os.environ["LIBRECHAT_JWT_TOKEN"] = _token_cache
            with open("../.librechat_token", "w") as f:
                f.write(_token_cache)
            with open(_cookies_path, "w") as f:
                for c in session.cookies:
                    f.write(f"{c.name}\t{c.value}\n")
            return _token_cache
    except Exception as e:
        print("[MCP] JWT refresh failed:", e)
    return None

def test_auth() -> dict:
    email = os.environ.get("LIBRECHAT_EMAIL")
    password = os.environ.get("LIBRECHAT_PASSWORD")
    if not email or not password:
        return {"success": False, "error": "LIBRECHAT_EMAIL and LIBRECHAT_PASSWORD must be set in environment."}
    session = requests.Session()
    try:
        resp = session.post(f"{API_BASE_URL}/auth/login", json={"email": email, "password": password})
    except Exception as e:
        return {"success": False, "error": f"Request failed: {e}"}
    result = {
        "status_code": resp.status_code,
        "response_text": resp.text,
        "success": False
    }
    try:
        resp.raise_for_status()
    except Exception as e:
        result["error"] = f"HTTP error: {e}"
        return result
    content_type = resp.headers.get("content-type", "")
    if "html" in content_type or resp.text.strip().startswith("<"):
        result["error"] = (
            "Response is HTML, not JSON. "
            "This usually means you are hitting the frontend, not the backend API. "
            "Check that LIBRECHAT_API_URL is set to the backend API, e.g. http://api:3080/api. "
            "Current value: '" + os.environ.get("LIBRECHAT_API_URL", "not set") + "'"
        )
        return result
    try:
        data = resp.json()
        result["json"] = data
        if data.get("twoFAPending"):
            result["error"] = "2FA is enabled for this account. Automated login is not supported."
        elif "token" in data:
            result["success"] = True
            with open(_cookies_path, "w") as f:
                for c in session.cookies:
                    f.write(f"{c.name}\t{c.value}\n")
        else:
            result["error"] = "No token in response JSON."
    except Exception as e:
        result["error"] = f"JSON decode error: {e}"
    return result


def resilient_request(method, url, **kwargs):
    """Make a request, log request/response, refresh JWT if expired, and retry once."""
    # Log request (excluding headers)
    body = None
    if 'json' in kwargs and kwargs['json'] is not None:
        body = kwargs['json']
    elif 'data' in kwargs and kwargs['data'] is not None:
        body = kwargs['data']
    print(f"[MCP] request: {method.upper()} {url}, body={body}")
    resp = requests.request(method, url, **kwargs)
    if resp.status_code == 401:
        print("[MCP] JWT expired, attempting refresh with cookies...")
        new_token = refresh_jwt_token_with_cookies()
        if new_token:
            # Update Authorization header and retry
            headers = kwargs.get("headers", {})
            headers["Authorization"] = f"Bearer {new_token}"
            kwargs["headers"] = headers
            print(f"[MCP] retry request: {method.upper()} {url}, body={body}")
            resp = requests.request(method, url, **kwargs)
    print(f"[MCP] response: status={resp.status_code}, content_type={resp.headers.get('content-type','')}, text={resp.text[:500]}")
    return resp
