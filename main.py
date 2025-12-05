import os
from fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.requests import Request
import inspect

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
    
    FastMCP doesn't expose get_asgi_app() publicly, but we can try to access
    it through internal attributes. FastMCP likely uses Starlette internally.
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
        # FastMCP might have a method that creates the app
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


def create_app_with_middleware():
    """
    Create an ASGI app with user context middleware.
    
    Since FastMCP doesn't expose get_asgi_app(), we'll try to:
    1. Get the app from FastMCP if possible
    2. Wrap it with middleware
    3. If that fails, use FastMCP.run() directly (without middleware)
    """
    # Try to get FastMCP's app
    fastmcp_app = get_fastmcp_app()
    
    if fastmcp_app:
        # Wrap with middleware
        app = Starlette(
            routes=[Mount("/", fastmcp_app)],
            middleware=[Middleware(UserContextMiddleware)]
        )
        return app
    else:
        # Fallback: return None to use FastMCP.run() directly
        # This means middleware won't work, but at least the server runs
        return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    os.environ["PORT"] = str(port)  # Ensure PORT is set for FastMCP

    # Try to create app with middleware
    app_with_middleware = create_app_with_middleware()
    
    if app_with_middleware:
        # Run with uvicorn and middleware
        print(f"Starting LibreChatMCP server with user context middleware on {host}:{port}")
        uvicorn.run(app_with_middleware, host=host, port=port)
    else:
        # Fallback: use FastMCP.run() directly (without middleware)
        # NOTE: This means user context extraction won't work via middleware
        # but we can still try to extract it in tools if FastMCP provides access
        print(f"Starting LibreChatMCP server (fallback mode) on {host}:{port}")
        print("WARNING: User context middleware not available. User context extraction may not work.")
        libre_chat_mcp.run(transport="http", host=host, port=port)
