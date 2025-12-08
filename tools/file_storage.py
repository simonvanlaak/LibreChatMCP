"""
File Storage Tools for LibreChat MCP Server

Provides user-isolated file storage with semantic search via RAG API integration.
All file operations are scoped to the authenticated user via user_id from request headers.
"""

import os
import json
import httpx
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from contextvars import ContextVar

# Storage and RAG API configuration
STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "/storage"))
RAG_API_URL = os.environ.get("RAG_API_URL", "http://librechat-rag-api:8000")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))

# User context using contextvars for thread-safe per-request storage
_user_id_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


def set_current_user(user_id: str):
    """Set the current user context for file operations (thread-safe)"""
    _user_id_context.set(user_id)


def get_current_user() -> str:
    """Get the current user ID or raise error if not authenticated"""
    user_id = _user_id_context.get()
    if not user_id:
        raise RuntimeError("User not authenticated. user_id must be set via X-User-ID header")
    
    # Reject placeholder strings (LibreChat bug: placeholders not replaced)
    if user_id.startswith("{{") and user_id.endswith("}}"):
        raise RuntimeError(
            f"Invalid user_id: '{user_id}' appears to be an unreplaced placeholder. "
            "This indicates LibreChat's processMCPEnv() didn't receive the user object. "
            "Please check LibreChat configuration or use OAuth authentication."
        )
    
    return user_id


def get_user_storage_path(user_id: str) -> Path:
    """Get the storage directory path for a user"""
    user_dir = STORAGE_ROOT / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_file_id(user_id: str, filename: str) -> str:
    """Generate a unique file ID for vectordb scoping"""
    return f"user_{user_id}_{filename}"


async def upload_file(filename: str, content: str) -> str:
    """
    Upload a file to user's storage and index it in RAG API.
    
    Args:
        filename: Name of the file to create
        content: Text content to write to the file
        
    Returns:
        Success message with file path
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    file_path = user_dir / filename
    
    # Check if file already exists
    if file_path.exists():
        return f"Error: File '{filename}' already exists. Use modify_file to update it."
    
    # Write file to storage
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(content)
    
    # Index in RAG API
    file_id = get_file_id(user_id, filename)
    metadata = {
        "user_id": user_id,
        "filename": filename,
        "created_at": datetime.utcnow().isoformat(),
        "size": len(content)
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RAG_API_URL}/embed",
                json={
                    "file_id": file_id,
                    "content": content,
                    "metadata": metadata,
                    "chunk_size": CHUNK_SIZE,
                    "chunk_overlap": CHUNK_OVERLAP
                }
            )
            response.raise_for_status()
    except Exception as e:
        # Clean up file if indexing failed
        file_path.unlink()
        raise RuntimeError(f"Failed to index file in RAG API: {e}")
    
    return f"Successfully uploaded '{filename}' ({len(content)} bytes) to {file_path}"


async def create_note(title: str, content: str) -> str:
    """
    Create a markdown note in user's storage.
    
    This is a convenience wrapper around upload_file that automatically adds .md extension
    and formats the note with a title header.
    
    Args:
        title: Title of the note (will be used as filename without .md extension)
        content: Content of the note (markdown formatted)
        
    Returns:
        Success message with file path
    """
    # Sanitize title for filename (remove special characters)
    import re
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    filename = f"{safe_title}.md"
    
    # Format note with title header
    note_content = f"# {title}\n\n{content}"
    
    # Use upload_file to create the note
    return await upload_file(filename, note_content)


async def list_files() -> str:
    """
    List all files in the user's storage with metadata.
    
    Returns:
        JSON formatted list of files with metadata
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    
    files = []
    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(file_path)
            })
    
    if not files:
        return "No files found in your storage."
    
    # Format as readable output
    output = f"Found {len(files)} file(s):\n\n"
    for f in sorted(files, key=lambda x: x['filename']):
        output += f"- {f['filename']}\n"
        output += f"  Size: {f['size']} bytes\n"
        output += f"  Modified: {f['modified']}\n\n"
    
    return output


async def read_file(filename: str) -> str:
    """
    Read the contents of a file from user's storage.
    
    Args:
        filename: Name of the file to read
        
    Returns:
        File contents as string
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    file_path = user_dir / filename
    
    if not file_path.exists():
        return f"Error: File '{filename}' not found in your storage."
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()
    
    return content


async def modify_file(filename: str, content: str) -> str:
    """
    Modify an existing file's contents and re-index in RAG API.
    
    Args:
        filename: Name of the file to modify
        content: New content to write
        
    Returns:
        Success message
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    file_path = user_dir / filename
    
    if not file_path.exists():
        return f"Error: File '{filename}' not found. Use upload_file to create new files."
    
    # Update file
    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
        await f.write(content)
    
    # Re-index in RAG API
    file_id = get_file_id(user_id, filename)
    metadata = {
        "user_id": user_id,
        "filename": filename,
        "modified_at": datetime.utcnow().isoformat(),
        "size": len(content)
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Delete old embeddings
            await client.delete(f"{RAG_API_URL}/embed/{file_id}")
            
            # Create new embeddings
            response = await client.post(
                f"{RAG_API_URL}/embed",
                json={
                    "file_id": file_id,
                    "content": content,
                    "metadata": metadata,
                    "chunk_size": CHUNK_SIZE,
                    "chunk_overlap": CHUNK_OVERLAP
                }
            )
            response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Failed to re-index file in RAG API: {e}")
    
    return f"Successfully modified '{filename}' ({len(content)} bytes)"


async def delete_file(filename: str) -> str:
    """
    Delete a file from storage and remove from RAG API index.
    
    Args:
        filename: Name of the file to delete
        
    Returns:
        Success message
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    file_path = user_dir / filename
    
    if not file_path.exists():
        return f"Error: File '{filename}' not found in your storage."
    
    # Remove from RAG API
    file_id = get_file_id(user_id, filename)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.delete(f"{RAG_API_URL}/embed/{file_id}")
    except Exception as e:
        print(f"Warning: Failed to remove file from RAG API: {e}")
        # Continue with file deletion even if RAG API deletion fails
    
    # Delete file
    file_path.unlink()
    
    return f"Successfully deleted '{filename}'"


async def search_files(query: str, max_results: int = 5) -> str:
    """
    Search user's files using semantic search via RAG API.
    
    Args:
        query: Search query text
        max_results: Maximum number of results to return (default: 5)
        
    Returns:
        Search results with relevant excerpts
    """
    user_id = get_current_user()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{RAG_API_URL}/query",
                json={
                    "query": query,
                    "filters": {
                        "user_id": user_id  # Only search this user's files
                    },
                    "top_k": max_results
                }
            )
            response.raise_for_status()
            results = response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to query RAG API: {e}")
    
    if not results or not results.get("results"):
        return f"No results found for query: '{query}'"
    
    # Format results
    output = f"Found {len(results['results'])} result(s) for '{query}':\n\n"
    for i, result in enumerate(results["results"], 1):
        metadata = result.get("metadata", {})
        filename = metadata.get("filename", "unknown")
        score = result.get("score", 0.0)
        excerpt = result.get("text", "")[:200]  # First 200 chars
        
        output += f"{i}. {filename} (score: {score:.3f})\n"
        output += f"   {excerpt}...\n\n"
    
    return output


async def auto_configure_obsidian_sync(
    user_id: str,
    repo_url: str,
    token: str,
    branch: str = "main"
) -> None:
    """
    Automatically configure Obsidian sync when credentials are provided via headers.
    This is called by middleware when customUserVars are set.
    
    Args:
        user_id: LibreChat user ID
        repo_url: Git repository URL
        token: Personal Access Token
        branch: Git branch name (defaults to "main")
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_dir = get_user_storage_path(user_id)
    config_path = user_dir / "git_config.json"
    temp_path = user_dir / "git_config.json.tmp"
    
    # Check if config already exists and is the same
    if config_path.exists():
        try:
            async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                existing_config = json.loads(content)
            # Only update if values changed
            if (existing_config.get("repo_url") == repo_url and
                existing_config.get("token") == token and
                existing_config.get("branch") == branch):
                return  # No changes needed
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Failed to read existing config for user {user_id}: {e}")
            # Proceed with write if read fails
    
    config = {
        "repo_url": repo_url,
        "token": token,
        "branch": branch,
        "updated_at": datetime.utcnow().isoformat(),
        "auto_configured": True,
        "version": "1.0"  # For future migrations
    }
    
    try:
        # Atomic write: write to temp file, then rename
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config, indent=2))
        temp_path.replace(config_path)  # Atomic rename
        logger.info(f"Auto-configured Obsidian sync for user {user_id}")
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"Failed to save sync configuration for user {user_id}: {e}")
        raise RuntimeError(f"Failed to save sync configuration: {e}")


async def configure_obsidian_sync(repo_url: str = None, token: str = None, branch: str = "main") -> str:
    """
    Configure Git Sync for Obsidian Vault.
    
    All parameters are optional. If not provided, the tool will:
    1. Check if already configured (returns existing config)
    2. If not configured, prompt user to set via customUserVars in UI settings
    
    This tool can be used to:
    - Check current configuration status
    - Update existing configuration
    - Configure manually (if customUserVars not used)
    
    Args:
        repo_url: HTTP(S) URL of the Git repository (optional)
        token: Personal Access Token (optional)
        branch: Branch to sync (default: "main", optional)
        
    Returns:
        Status message with current configuration or success message
    """
    user_id = get_current_user()
    user_dir = get_user_storage_path(user_id)
    config_path = user_dir / "git_config.json"
    
    # If no parameters provided, check if already configured
    if not repo_url or not token:
        if config_path.exists():
            try:
                async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    existing_config = json.loads(content)
                repo = existing_config.get('repo_url', 'unknown')
                auto_configured = existing_config.get('auto_configured', False)
                config_source = "auto-configured via customUserVars" if auto_configured else "manually configured"
                return (
                    f"Obsidian sync is already configured for repository: {repo}\n"
                    f"Configuration was {config_source}.\n"
                    f"To update, provide new repo_url and/or token parameters, or update customUserVars in UI settings."
                )
            except Exception as e:
                return (
                    f"No Obsidian sync configuration found.\n"
                    f"To configure, either:\n"
                    f"1. Set customUserVars in UI settings (OBSIDIAN_REPO_URL, OBSIDIAN_TOKEN, OBSIDIAN_BRANCH) - recommended\n"
                    f"2. Provide repo_url and token parameters to this tool\n"
                    f"Error reading existing config: {e}"
                )
        else:
            return (
                "No Obsidian sync configuration found.\n"
                "To configure, either:\n"
                "1. Set customUserVars in UI settings (OBSIDIAN_REPO_URL, OBSIDIAN_TOKEN, OBSIDIAN_BRANCH) - recommended\n"
                "2. Provide repo_url and token parameters to this tool"
            )
    
    # Parameters provided - update/create configuration
    config = {
        "repo_url": repo_url,
        "token": token,
        "branch": branch,
        "updated_at": datetime.utcnow().isoformat(),
        "auto_configured": False,
        "version": "1.0"
    }
    
    temp_path = user_dir / "git_config.json.tmp"
    try:
        # Use atomic write pattern for consistency
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(config, indent=2))
        temp_path.replace(config_path)  # Atomic rename
        return f"Successfully configured Obsidian Sync for repository: {repo_url}"
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Failed to save sync configuration: {e}")
