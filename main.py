import os
from fastmcp import FastMCP
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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
from tools.file_storage import (
    upload_file,
    create_note,
    list_files,
    read_file,
    modify_file,
    delete_file,
    search_files,
    set_current_user,
)
# Obsidian sync tools removed - now in separate ObsidianSyncMCP service

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
libre_chat_mcp.tool(upload_file)
libre_chat_mcp.tool(create_note)
libre_chat_mcp.tool(list_files)
libre_chat_mcp.tool(read_file)
libre_chat_mcp.tool(modify_file)
libre_chat_mcp.tool(delete_file)
libre_chat_mcp.tool(search_files)
# Obsidian sync tools removed - now in separate ObsidianSyncMCP service


class SetUserIdFromHeaderMiddleware(BaseHTTPMiddleware):
    """
    Simplified middleware for LibreChatMCP.
    Extracts user ID from headers or query parameters.
    OAuth removed - now handled by ObsidianSyncMCP for obsidian sync features.
    """
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        import logging
        import json
        logger = logging.getLogger(__name__)
        
        user_id = None
        
        # Method 1: Header-based extraction
        user_id = request.headers.get("x-user-id")
        
        # Method 2: URL query parameter (fallback)
        if not user_id or user_id == "{{LIBRECHAT_USER_ID}}":
            query_user_id = request.query_params.get("userId") or request.query_params.get("user_id")
            
            if query_user_id and query_user_id != "{{LIBRECHAT_USER_ID}}":
                user_id = query_user_id
                logger.info(f"✅ Extracted user_id from URL query parameter: {user_id}")
            else:
                logger.debug(f"Query parameter 'userId' not found or is placeholder")
        
        # Method 3: Request body extraction (fallback)
        if not user_id or user_id == "{{LIBRECHAT_USER_ID}}":
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_data = json.loads(body_bytes)
                    if isinstance(body_data, dict):
                        params = body_data.get("params", {})
                        if isinstance(params, dict):
                            user_id = params.get("userId") or params.get("user_id") or params.get("user")
                            if user_id:
                                logger.info(f"Extracted user_id from request body: {user_id}")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"Could not extract user_id from request body: {e}")
        
        # Only set user_id if it's valid (not None and not a placeholder)
        if user_id and not (user_id.startswith("{{") and user_id.endswith("}}")):
            set_current_user(user_id)
        else:
            set_current_user(None)
            if not user_id or user_id == "{{LIBRECHAT_USER_ID}}":
                logger.warning(f"User ID extraction failed. Tried: X-User-ID header, URL query parameter, request body")
                logger.warning(f"Final user_id value: {user_id}")
        
        response = await call_next(request)
        set_current_user(None)
        return response


# Create the app
base_app = libre_chat_mcp.http_app()

# Wrap with middleware (OAuth removed - simplified)
app = SetUserIdFromHeaderMiddleware(base_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting LibreChatMCP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
