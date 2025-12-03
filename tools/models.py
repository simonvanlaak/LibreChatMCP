import os
from tools.auth import default_headers, resilient_request

API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")

def get_models() -> dict:
    """
    Get a list of all models available on the server.

    Returns:
        dict: List of models and their metadata.

    Example:
        get_models()
    """
    url = f"{API_BASE_URL}/models"
    headers = default_headers()
    resp = resilient_request("get", url, headers=headers)
    resp.raise_for_status()
    return resp.json()
