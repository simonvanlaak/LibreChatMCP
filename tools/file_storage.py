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
