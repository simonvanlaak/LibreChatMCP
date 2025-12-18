import os
from fastmcp import FastMCP
import uvicorn

from tools.agent import (
    create_agent,
    list_agents,
    get_agent,
    update_agent,
    delete_agent,
    list_agent_categories,
    list_agent_tools,
)
from tools.model_context_protocol import (
    get_model_context_protocol_tools, get_model_context_protocol_info, get_model_context_protocol_status)
from tools.models import get_models
libre_chat_mcp = FastMCP("LibreChat MCP Server", stateless_http=True)

# Register all tools
libre_chat_mcp.tool(create_agent)
libre_chat_mcp.tool(list_agents)
libre_chat_mcp.tool(get_agent)
libre_chat_mcp.tool(update_agent)
libre_chat_mcp.tool(delete_agent)
libre_chat_mcp.tool(list_agent_categories)
libre_chat_mcp.tool(list_agent_tools)
libre_chat_mcp.tool(get_model_context_protocol_tools)
libre_chat_mcp.tool(get_model_context_protocol_status)
libre_chat_mcp.tool(get_model_context_protocol_info)
libre_chat_mcp.tool(get_models)

# Create the app
app = libre_chat_mcp.http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting LibreChatMCP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
