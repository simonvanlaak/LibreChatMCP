import os
from fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount
import inspect
import auth

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
    configure_obsidian_sync,
)
from middleware.user_context import UserContextMiddleware

libre_chat_mcp = FastMCP("LibreChat MCP Server", stateless_http=True)

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
libre_chat_mcp.tool(configure_obsidian_sync)


def get_fastmcp_app_and_instance():
    """
    Get the underlying ASGI app from FastMCP and the FastMCP instance.
    """
    try:
        # Prefer the documented method: http_app(), always pass lifespan
        if hasattr(libre_chat_mcp, "http_app"):
            # Pass lifespan explicitly to ensure proper initialization
            asgi_app = libre_chat_mcp.http_app(lifespan=libre_chat_mcp.lifespan)
            return asgi_app, libre_chat_mcp
        # Fallback to legacy extraction
        for attr_name in ['_app', 'app', '__app__']:
            if hasattr(libre_chat_mcp, attr_name):
                attr = getattr(libre_chat_mcp, attr_name)
                if callable(attr):
                    sig = inspect.signature(attr)
                    if len(sig.parameters) == 3:
                        return attr, libre_chat_mcp
    except Exception as e:
        print(f"Warning: Could not access FastMCP app: {e}")
    return None, None


def create_app():
    """
    Create the main Starlette app with OAuth routes and FastMCP mounted.
    """
    fastmcp_app, fastmcp_instance = get_fastmcp_app_and_instance()
    if not fastmcp_app or not fastmcp_instance:
        print("CRITICAL ERROR: Could not extract ASGI app from FastMCP.")
        return None
    routes = [
        Mount("/", app=fastmcp_app),
    ]
    # Add Auth routes
    routes.extend(auth.routes)
    # Use the FastMCP instance's lifespan property as recommended
    app = Starlette(
        routes=routes,
        middleware=[Middleware(UserContextMiddleware)],
        lifespan=getattr(fastmcp_instance, "lifespan", None)  # Pass FastMCP lifespan explicitly
    )
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    os.environ["PORT"] = str(port)

    app = create_app()
    
    if app:
        print(f"Starting LibreChatMCP server (OAuth Enabled) on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    else:
        # Fallback to direct FastMCP run (no Auth)
        print(f"Starting LibreChatMCP server (Fallback Mode - No Auth) on {host}:{port}")
        libre_chat_mcp.run(transport="http", host=host, port=port)
