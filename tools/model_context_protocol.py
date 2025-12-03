import os
from tools.auth import default_headers, resilient_request

API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")


def get_model_context_protocol_tools() -> dict:
    """
    Get a list of all Model Context Protocol tools available on the server.

    Returns:
        dict: List of Model Context Protocol tools and their metadata.

    Example:
        get_model_context_protocol_tools()
    """
    url = f"{API_BASE_URL}/mcp/tools"
    headers = default_headers()
    resp = resilient_request("get", url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_model_context_protocol_status() -> dict:
    """
    Get the status of the Model Context Protocol server.

    Returns:
        dict: Model Context Protocol server status information.

    Example:
        get_model_context_protocol_status()
    """
    url = f"{API_BASE_URL}/mcp/status"
    headers = default_headers()
    resp = resilient_request("get", url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_model_context_protocol_info() -> dict:
    """
    Get general information about the Model Context Protocol server.

    Returns:
        dict: Model Context Protocol server info and metadata.

    Example:
        get_model_context_protocol_info()
    """
    url = f"{API_BASE_URL}/mcp/info"
    headers = default_headers()
    resp = resilient_request("get", url, headers=headers)
    resp.raise_for_status()
    return resp.json()

