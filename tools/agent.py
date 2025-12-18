import os
from .auth import default_headers, resilient_request

API_BASE_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")

# Agent endpoint is implemented in LibreChat/api/server/controllers/agents/v1.js

def list_agents(page: int = 1, limit: int = 10) -> dict:
    """
    List agents with pagination.

    Args:
        page (int): The page number to retrieve. Defaults to 1.
        limit (int): The number of agents per page. Defaults to 10.

    Returns:
        dict: JSON object with agent data or error message.

    Example:
        list_agents(page=1, limit=10)
    """
    headers = default_headers()
    url = f"{API_BASE_URL}/agents"
    resp = resilient_request("get", url, params={"page": page, "limit": limit}, headers=headers)
    try:
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type:
            return {
                "success": False,
                "error": f"Non-JSON response: {resp.text}",
                "status_code": resp.status_code,
                "content_type": content_type
            }
        return resp.json()
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception: {e}",
            "status_code": resp.status_code,
            "response_text": resp.text
        }

def create_agent(
    name: str = None,
    description: str = None,
    instructions: str = None,
    avatar: dict = None,
    model_parameters: dict = None,
    tools: list = None,
    agent_ids: list = None,
    edges: list = None,
    end_after_tools: bool = None,
    hide_sequential_outputs: bool = None,
    artifacts: str = None,
    recursion_limit: int = None,
    conversation_starters: list = None,
    tool_resources: dict = None,
    support_contact: dict = None,
    category: str = None,
    provider: str = None,
    model: str = None,
    projectIds: list = None,
    removeProjectIds: list = None,
    isCollaborative: bool = None
) -> dict:
    """
    Create a new agent in LibreChat.

    Args:
        name (str, optional): Agent name.
        description (str, optional): Agent description.
        instructions (str, optional): System instructions for the agent.
        avatar (dict, optional): Avatar object with 'filepath' and 'source'.
        model_parameters (dict, optional): Model-specific parameters.
        tools (list of str, optional): List of tool names.
        agent_ids (list of str, optional): Deprecated, use 'edges' instead.
        edges (list of dict, optional): Graph edges for agent handoffs.
        end_after_tools (bool, optional): End conversation after tools run.
        hide_sequential_outputs (bool, optional): Hide outputs from sequential tool runs.
        artifacts (str, optional): Artifact string.
        recursion_limit (int, optional): Max recursion depth for agent.
        conversation_starters (list of str, optional): Conversation starter prompts.
        tool_resources (dict, optional): Tool resources (see agentToolResourcesSchema).
        support_contact (dict, optional): Support contact info (name, email).
        category (str, optional): Agent category.
        provider (str, required): Provider name (e.g., 'openai').
        model (str or None, required): Model name or None.
        projectIds (list of str, optional): Project IDs to add.
        removeProjectIds (list of str, optional): Project IDs to remove.
        isCollaborative (bool, optional): Collaborative flag.

    Returns:
        dict: The created agent object as returned by the LibreChat API.

    Raises:
        requests.HTTPError: If the API call fails.

    Example:
        create_agent(
            name="MyAgent",
            provider="openai",
            model="gpt-4",
            tools=["file_search"],
            avatar={"filepath": "/path/to/avatar.png", "source": "upload"}
        )
    """
    agent_fields = {}
    for k, v in [
        ("name", name),
        ("description", description),
        ("instructions", instructions),
        ("avatar", avatar),
        ("model_parameters", model_parameters),
        ("tools", tools),
        ("agent_ids", agent_ids),
        ("edges", edges),
        ("end_after_tools", end_after_tools),
        ("hide_sequential_outputs", hide_sequential_outputs),
        ("artifacts", artifacts),
        ("recursion_limit", recursion_limit),
        ("conversation_starters", conversation_starters),
        ("tool_resources", tool_resources),
        ("support_contact", support_contact),
        ("category", category),
        ("provider", provider),
        ("model", model),
        ("projectIds", projectIds),
        ("removeProjectIds", removeProjectIds),
        ("isCollaborative", isCollaborative)
    ]:
        if v is not None:
            agent_fields[k] = v
    resp = resilient_request("post", f"{API_BASE_URL}/agents", json=agent_fields, headers=default_headers())
    resp.raise_for_status()
    return resp.json()


def get_agent(agent_id: str) -> dict:
    """
    Get information about a specific agent by ID.

    Args:
        agent_id (str): The ID of the agent.

    Returns:
        dict: The agent object if found.

    Example:
        get_agent("agent_T2q20k1pGasRXO9KWapgN")
    """
    resp = resilient_request("get", f"{API_BASE_URL}/agents/{agent_id}", headers=default_headers())
    resp.raise_for_status()
    return resp.json()

def update_agent(
    agent_id: str,
    name: str = None,
    description: str = None,
    instructions: str = None,
    avatar: dict = None,
    model_parameters: dict = None,
    tools: list = None,
    agent_ids: list = None,
    edges: list = None,
    end_after_tools: bool = None,
    hide_sequential_outputs: bool = None,
    artifacts: str = None,
    recursion_limit: int = None,
    conversation_starters: list = None,
    tool_resources: dict = None,
    support_contact: dict = None,
    category: str = None,
    provider: str = None,
    model: str = None,
    projectIds: list = None,
    removeProjectIds: list = None,
    isCollaborative: bool = None
) -> dict:
    """
    Update an existing agent in LibreChat.

    Only 'agent_id' is required; all other fields are optional and will be updated if provided.
    Use the list_agents tool to find available agent IDs.
    To learn about the current config of an agent use the get_agent tool.

    Args:
        agent_id (str, required): The ID of the agent to update. Use the list_agents tool to find available agent IDs.
        name (str, optional): Agent name.
        description (str, optional): Agent description.
        instructions (str, optional): System instructions for the agent.
        avatar (dict, optional): Avatar object with 'filepath' and 'source'.
        model_parameters (dict, optional): Model-specific parameters.
        tools (list of str, optional): List of tool names.
        agent_ids (list of str, optional): Deprecated, use 'edges' instead.
        edges (list of dict, optional): Graph edges for agent handoffs.
        end_after_tools (bool, optional): End conversation after tools run.
        hide_sequential_outputs (bool, optional): Hide outputs from sequential tool runs.
        artifacts (str, optional): Artifact string.
        recursion_limit (int, optional): Max recursion depth for agent.
        conversation_starters (list of str, optional): Conversation starter prompts.
        tool_resources (dict, optional): Tool resources (see agentToolResourcesSchema).
        support_contact (dict, optional): Support contact info (name, email).
        category (str, optional): Agent category.
        provider (str, optional): Provider name (e.g., 'openai').
        model (str or None, optional): Model name or None.
        projectIds (list of str, optional): Project IDs to add.
        removeProjectIds (list of str, optional): Project IDs to remove.
        isCollaborative (bool, optional): Collaborative flag.

    Returns:
        dict: The updated agent object as returned by the LibreChat API.

    Raises:
        requests.HTTPError: If the API call fails.

    Example:
        update_agent(
            agent_id="agent_123",
            name="UpdatedAgent",
            tools=["file_search"],
            isCollaborative=True
        )
    """
    update_fields = {}
    for k, v in [
        ("name", name),
        ("description", description),
        ("instructions", instructions),
        ("avatar", avatar),
        ("model_parameters", model_parameters),
        ("tools", tools),
        ("agent_ids", agent_ids),
        ("edges", edges),
        ("end_after_tools", end_after_tools),
        ("hide_sequential_outputs", hide_sequential_outputs),
        ("artifacts", artifacts),
        ("recursion_limit", recursion_limit),
        ("conversation_starters", conversation_starters),
        ("tool_resources", tool_resources),
        ("support_contact", support_contact),
        ("category", category),
        ("provider", provider),
        ("model", model),
        ("projectIds", projectIds),
        ("removeProjectIds", removeProjectIds),
        ("isCollaborative", isCollaborative)
    ]:
        if v is not None:
            update_fields[k] = v
    if not update_fields:
        raise ValueError(
            "update_agent: No update fields provided. "
            "You must specify at least one field to update (besides agent_id). "
            "All update parameters were None or missing. "
            "Example: update_agent(agent_id='...', name='New Name')"
        )
    url = f"{API_BASE_URL}/agents/{agent_id}"
    resp = resilient_request("patch", url, json=update_fields, headers=default_headers())
    resp.raise_for_status()
    return resp.json()

def delete_agent(agent_id: str) -> dict:
    """
    Delete an agent by ID.

    Args:
        agent_id (str): The ID of the agent to delete.

    Returns:
        dict: Confirmation of deletion.

    Example:
        delete_agent("agent_T2q20k1pGasRXO9KWapgN")
    """
    resp = resilient_request("delete", f"{API_BASE_URL}/agents/{agent_id}", headers=default_headers())
    resp.raise_for_status()
    return resp.json()

def list_agent_categories() -> list:
    """
    List all agent categories.

    Returns:
        list: List of agent categories with counts and descriptions.

    Example:
        list_agent_categories()
    """
    resp = resilient_request("get", f"{API_BASE_URL}/agents/categories", headers=default_headers())
    resp.raise_for_status()
    return resp.json()

def list_agent_tools() -> list:
    """
    List all available tools for agents.

    Returns:
        list: List of available agent tools.

    Example:
        list_agent_tools()
    """
    resp = resilient_request("get", f"{API_BASE_URL}/agents/tools", headers=default_headers())
    resp.raise_for_status()
    return resp.json()
