"""A2A protocol translation module."""
from typing import Dict, Any, Optional
import json


def mcp_to_a2a_task(
    message: str,
    task_id: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert MCP chat message to A2A Task format.
    
    Args:
        message: User message from MCP
        task_id: Optional task ID (will be generated if not provided)
        parent_id: Optional parent task ID
        
    Returns:
        A2A Task dictionary
    """
    return {
        "task_id": task_id,
        "parent_id": parent_id,
        "type": "chat",
        "payload": {
            "message": message,
        },
        "required_capabilities": None,
    }


def a2a_response_to_mcp(
    a2a_response: Dict[str, Any],
) -> str:
    """
    Convert A2A response to MCP message format.
    
    Args:
        a2a_response: A2A response dictionary
        
    Returns:
        MCP message string
    """
    if a2a_response.get("status") == "error":
        error = a2a_response.get("error", "Unknown error")
        return f"Error: {error}"
    
    result = a2a_response.get("result", {})
    message = result.get("message", "")
    return message


def parse_a2a_stream_chunk(chunk_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse A2A streaming chunk (Server-Sent Events format).
    
    Args:
        chunk_data: SSE data line (e.g., "data: {...}")
        
    Returns:
        Parsed chunk dictionary or None if invalid
    """
    if not chunk_data.startswith("data: "):
        return None
    
    try:
        json_str = chunk_data[6:]  # Remove "data: " prefix
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

