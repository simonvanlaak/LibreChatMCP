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
)
from middleware.user_context import UserContextMiddleware

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


def get_fastmcp_app():
    """
    Get the underlying ASGI app from FastMCP.
    """
    # Try multiple ways to access the internal app
    try:
        # Method 1: Direct attribute access
        for attr_name in ['_app', 'app', '__app__']:
            if hasattr(libre_chat_mcp, attr_name):
                attr = getattr(libre_chat_mcp, attr_name)
                if callable(attr):
                    # Check if it looks like an ASGI app
                    sig = inspect.signature(attr)
                    if len(sig.parameters) == 3:  # ASGI: (scope, receive, send)
                        return attr
        
        # Method 2: Access through transport
        for transport_attr in ['_transport', 'transport', '_http_transport']:
            if hasattr(libre_chat_mcp, transport_attr):
                transport = getattr(libre_chat_mcp, transport_attr)
                for app_attr in ['app', '_app', '_asgi_app']:
                    if hasattr(transport, app_attr):
                        attr = getattr(transport, app_attr)
                        if callable(attr):
                            sig = inspect.signature(attr)
                            if len(sig.parameters) == 3:
                                return attr
        
        # Method 3: Try to call internal method to create app
        for method_name in ['_create_app', '_get_app', 'get_asgi_app', '_build_app']:
            if hasattr(libre_chat_mcp, method_name):
                method = getattr(libre_chat_mcp, method_name)
                if callable(method):
                    try:
                        app = method()
                        if callable(app):
                            sig = inspect.signature(app)
                            if len(sig.parameters) == 3:
                                return app
                    except Exception:
                        pass
    except Exception as e:
        print(f"Warning: Could not access FastMCP app: {e}")
    
    return None


def create_app():
    """
    Create the main Starlette app with OAuth routes and FastMCP mounted.
    """
    fastmcp_app = get_fastmcp_app()
    
    if not fastmcp_app:
        print("CRITICAL ERROR: Could not extract ASGI app from FastMCP.")
        # Fallback to just running FastMCP raw if this fails, but Auth won't work
        return None

    routes = [
        Mount("/mcp", app=fastmcp_app), # Mount FastMCP at /mcp
    ]
    
    # Add Auth routes
    routes.extend(auth.routes)

    app = Starlette(
        routes=routes,
        middleware=[Middleware(UserContextMiddleware)]
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
