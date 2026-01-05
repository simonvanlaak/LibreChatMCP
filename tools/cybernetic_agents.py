"""A2A protocol client for Cybernetic Agents communication."""
import os
import httpx
from typing import Optional
from .a2a_translator import mcp_to_a2a_task, a2a_response_to_mcp, parse_a2a_stream_chunk

# System 5 service URL (Kubernetes service discovery)
SYSTEM5_SERVICE_URL = os.environ.get(
    "SYSTEM5_SERVICE_URL",
    "http://system5-service.cybernetic-agents.svc.cluster.local:8080"
)


def chat_with_cybernetic_agent(
    message: str,
    agent_id: Optional[str] = None,
) -> str:
    """
    Chat with a Cybernetic Agent (System 5) via A2A protocol.
    
    This tool translates MCP chat messages to A2A Task format, sends them to System 5,
    and returns the streaming response.
    
    Args:
        message: The chat message to send to the agent
        agent_id: Optional agent ID (defaults to system-5-root)
        
    Returns:
        The agent's response message
        
    Example:
        chat_with_cybernetic_agent("Hello, how are you?")
    """
    if not message:
        return "Error: Message cannot be empty"
    
    agent_id = agent_id or "system-5-root"
    
    # Translate MCP message to A2A Task
    a2a_task = mcp_to_a2a_task(message)
    
    # Send A2A request to System 5 (using sync httpx client)
    try:
        with httpx.Client(timeout=60.0) as client:
            url = f"{SYSTEM5_SERVICE_URL}/a2a/v1/task"
            
            # Send request and stream response
            with client.stream("POST", url, json=a2a_task) as response:
                response.raise_for_status()
                
                # Collect streaming chunks
                full_response = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    # Parse SSE chunk
                    chunk_data = parse_a2a_stream_chunk(line)
                    if chunk_data:
                        # Check if this is a text chunk
                        if "chunk" in chunk_data:
                            full_response += chunk_data["chunk"]
                        # Check if this is the final response
                        elif chunk_data.get("status") == "complete":
                            result = chunk_data.get("result", {})
                            if "message" in result:
                                full_response = result["message"]
                            break
                
                return full_response if full_response else "No response received"
                
    except httpx.TimeoutException:
        return "Error: Request to System 5 agent timed out"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error: Failed to communicate with System 5 agent: {str(e)}"

