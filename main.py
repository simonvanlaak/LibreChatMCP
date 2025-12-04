import os
from fastmcp import FastMCP

from tools.agent import (
    create_agent,
    list_agents,
    get_agent,
    update_agent,
    delete_agent,
    list_agent_categories,
    list_agent_tools,
)
from tools.model_context_protocol import (get_model_context_protocol_tools, get_model_context_protocol_info, get_model_context_protocol_status)
from tools.models import get_models
from tools.file_storage import (
    upload_file,
    create_note,
    list_files,
    read_file,
    modify_file,
    delete_file,
    search_files,
)

libre_chat_mcp = FastMCP("LibreChat MCP Server")

# Register Agent tools
libre_chat_mcp.tool(create_agent)
libre_chat_mcp.tool(list_agents)
libre_chat_mcp.tool(get_agent)
libre_chat_mcp.tool(update_agent)
libre_chat_mcp.tool(delete_agent)
libre_chat_mcp.tool(list_agent_categories)
libre_chat_mcp.tool(list_agent_tools)
# Register MCP tools
libre_chat_mcp.tool(get_model_context_protocol_tools)
libre_chat_mcp.tool(get_model_context_protocol_status)
libre_chat_mcp.tool(get_model_context_protocol_info)
# Register Models tools
libre_chat_mcp.tool(get_models)
# Register File Storage tools
libre_chat_mcp.tool(upload_file)
libre_chat_mcp.tool(create_note)
libre_chat_mcp.tool(list_files)
libre_chat_mcp.tool(read_file)
libre_chat_mcp.tool(modify_file)
libre_chat_mcp.tool(delete_file)
libre_chat_mcp.tool(search_files)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    os.environ["PORT"] = str(port)  # Ensure PORT is set for FastMCP

    # NOTE:
    # The current version of FastMCP used here does not expose a `get_asgi_app`
    # method on the FastMCP instance, which caused the container to crash with:
    #   AttributeError: 'FastMCP' object has no attribute 'get_asgi_app'
    #
    # To keep the service running reliably, we start FastMCP directly without
    # attempting to access the underlying ASGI app for now.
    # If a public API to access the ASGI app is added in the future, this is
    # where custom middleware such as `UserContextMiddleware` should be wired in.

    # Run the server
    libre_chat_mcp.run(transport="http", host=host, port=port)
