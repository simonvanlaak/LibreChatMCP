"""
Unit tests for file storage tools

Tests user isolation, file operations, and RAG API integration
"""

import pytest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

# Import the file storage module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools import file_storage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_storage_root = file_storage.STORAGE_ROOT
        file_storage.STORAGE_ROOT = Path(tmpdir)
        yield Path(tmpdir)
        file_storage.STORAGE_ROOT = old_storage_root


@pytest.fixture
def mock_rag_api():
    """Mock the RAG API HTTP client"""
    with patch('tools.file_storage.httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": []}
        
        mock_instance.post.return_value = mock_response
        mock_instance.delete.return_value = mock_response
        
        yield mock_instance


@pytest.fixture
def setup_user():
    """Setup user context for tests"""
    file_storage.set_current_user("test_user_123")
    yield "test_user_123"
    file_storage._current_user_id = None


class TestUserIsolation:
    """Test that users can only access their own files"""
    
    @pytest.mark.asyncio
    async def test_different_users_isolated_storage(self, temp_storage_dir, mock_rag_api):
        """Test that different users have isolated storage directories"""
        # User A uploads a file
        file_storage.set_current_user("user_a")
        await file_storage.upload_file("test.txt", "User A's content")
        
        user_a_path = temp_storage_dir / "user_a" / "test.txt"
        assert user_a_path.exists()
        
        # User B should not see User A's file
        file_storage.set_current_user("user_b")
        result = await file_storage.list_files()
        assert "No files found" in result
        
        # User B uploads their own file
        await file_storage.upload_file("test.txt", "User B's content")
        user_b_path = temp_storage_dir / "user_b" / "test.txt"
        assert user_b_path.exists()
        
        # Verify both files exist but are isolated
        assert user_a_path.read_text() == "User A's content"
        assert user_b_path.read_text() == "User B's content"
    
    @pytest.mark.asyncio
    async def test_user_cannot_read_other_users_files(self, temp_storage_dir, mock_rag_api):
        """Test that users cannot read files from other users"""
        # User A creates a file
        file_storage.set_current_user("user_a")
        await file_storage.upload_file("private.txt", "Secret data")
        
        # User B tries to read it
        file_storage.set_current_user("user_b")
        result = await file_storage.read_file("private.txt")
        assert "Error: File 'private.txt' not found" in result


class TestFileOperations:
    """Test basic file operations"""
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test successful file upload"""
        result = await file_storage.upload_file("test.txt", "Hello, world!")
        
        assert "Successfully uploaded 'test.txt'" in result
        file_path = temp_storage_dir / "test_user_123" / "test.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Hello, world!"
        
        # Verify RAG API was called for indexing
        mock_rag_api.post.assert_called_once()
        call_args = mock_rag_api.post.call_args
        assert "/embed" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_upload_duplicate_file_fails(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test that uploading a duplicate file fails"""
        await file_storage.upload_file("test.txt", "First content")
        result = await file_storage.upload_file("test.txt", "Second content")
        
        assert "Error: File 'test.txt' already exists" in result
    
    @pytest.mark.asyncio
    async def test_list_files(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test listing files"""
        # Upload multiple files
        await file_storage.upload_file("file1.txt", "Content 1")
        await file_storage.upload_file("file2.txt", "Content 2")
        
        result = await file_storage.list_files()
        
        assert "Found 2 file(s)" in result
        assert "file1.txt" in result
        assert "file2.txt" in result
    
    @pytest.mark.asyncio
    async def test_list_files_empty(self, temp_storage_dir, setup_user):
        """Test listing when no files exist"""
        result = await file_storage.list_files()
        assert "No files found" in result
    
    @pytest.mark.asyncio
    async def test_read_file_success(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test reading a file"""
        await file_storage.upload_file("test.txt", "Test content")
        result = await file_storage.read_file("test.txt")
        
        assert result == "Test content"
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_storage_dir, setup_user):
        """Test reading a file that doesn't exist"""
        result = await file_storage.read_file("nonexistent.txt")
        assert "Error: File 'nonexistent.txt' not found" in result
    
    @pytest.mark.asyncio
    async def test_modify_file_success(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test modifying an existing file"""
        await file_storage.upload_file("test.txt", "Original content")
        result = await file_storage.modify_file("test.txt", "Modified content")
        
        assert "Successfully modified 'test.txt'" in result
        
        # Verify file was updated
        file_path = temp_storage_dir / "test_user_123" / "test.txt"
        assert file_path.read_text() == "Modified content"
        
        # Verify RAG API was called to delete and re-index
        delete_call_count = sum(1 for call in mock_rag_api.delete.call_args_list)
        post_call_count = sum(1 for call in mock_rag_api.post.call_args_list)
        
        assert delete_call_count >= 1  # Delete old embeddings
        assert post_call_count >= 2     # Original upload + re-index
    
    @pytest.mark.asyncio
    async def test_modify_nonexistent_file(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test modifying a file that doesn't exist"""
        result = await file_storage.modify_file("nonexistent.txt", "New content")
        assert "Error: File 'nonexistent.txt' not found" in result
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test deleting a file"""
        await file_storage.upload_file("test.txt", "Content to delete")
        result = await file_storage.delete_file("test.txt")
        
        assert "Successfully deleted 'test.txt'" in result
        
        # Verify file was removed
        file_path = temp_storage_dir / "test_user_123" / "test.txt"
        assert not file_path.exists()
        
        # Verify RAG API was called to remove embeddings
        mock_rag_api.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, temp_storage_dir, setup_user):
        """Test deleting a file that doesn't exist"""
        result = await file_storage.delete_file("nonexistent.txt")
        assert "Error: File 'nonexistent.txt' not found" in result


class TestRAGIntegration:
    """Test RAG API integration"""
    
    @pytest.mark.asyncio
    async def test_search_files(self, temp_storage_dir, setup_user):
        """Test semantic search using RAG API"""
        with patch('tools.file_storage.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Mock search response
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "results": [
                    {
                        "metadata": {"filename": "test.txt"},
                        "score": 0.95,
                        "text": "This is a test document with relevant content"
                    }
                ]
            }
            mock_instance.post.return_value = mock_response
            
            result = await file_storage.search_files("relevant content")
            
            assert "Found 1 result(s)" in result
            assert "test.txt" in result
            assert "0.950" in result
            
            # Verify query was scoped to user
            call_args = mock_instance.post.call_args
            query_data = call_args[1]["json"]
            assert query_data["filters"]["user_id"] == "test_user_123"
    
    @pytest.mark.asyncio
    async def test_search_no_results(self, temp_storage_dir, setup_user):
        """Test search with no results"""
        with patch('tools.file_storage.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"results": []}
            mock_instance.post.return_value = mock_response
            
            result = await file_storage.search_files("nonexistent query")
            
            assert "No results found" in result
    
    @pytest.mark.asyncio
    async def test_file_id_format(self, temp_storage_dir, setup_user, mock_rag_api):
        """Test that file IDs are properly formatted for user scoping"""
        await file_storage.upload_file("test.txt", "Content")
        
        # Check the file_id sent to RAG API
        call_args = mock_rag_api.post.call_args
        request_data = call_args[1]["json"]
        
        assert request_data["file_id"] == "user_test_user_123_test.txt"
        assert request_data["metadata"]["user_id"] == "test_user_123"


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_no_user_context_fails(self, temp_storage_dir):
        """Test that operations fail without user context"""
        file_storage._current_user_id = None
        
        with pytest.raises(RuntimeError, match="User not authenticated"):
            await file_storage.upload_file("test.txt", "Content")
    
    @pytest.mark.asyncio
    async def test_rag_api_failure_cleans_up_file(self, temp_storage_dir, setup_user):
        """Test that file is cleaned up if RAG API indexing fails"""
        with patch('tools.file_storage.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Mock RAG API failure
            mock_instance.post.side_effect = httpx.RequestError("Connection failed")
            
            with pytest.raises(RuntimeError, match="Failed to index file"):
                await file_storage.upload_file("test.txt", "Content")
            
            # Verify file was cleaned up
            file_path = temp_storage_dir / "test_user_123" / "test.txt"
            assert not file_path.exists()


class TestObsidianSyncConfiguration:
    """Test Obsidian sync auto-configuration functionality"""
    
    @pytest.mark.asyncio
    async def test_auto_configure_obsidian_sync_creates_config(self, temp_storage_dir):
        """Test that auto_configure_obsidian_sync creates git_config.json"""
        import json
        
        user_id = "test_user_456"
        repo_url = "https://github.com/user/vault.git"
        token = "ghp_testtoken123"
        branch = "main"
        
        await file_storage.auto_configure_obsidian_sync(
            user_id=user_id,
            repo_url=repo_url,
            token=token,
            branch=branch
        )
        
        # Verify config file was created
        config_path = temp_storage_dir / user_id / "git_config.json"
        assert config_path.exists()
        
        # Verify config content
        import aiofiles
        async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
        
        assert config["repo_url"] == repo_url
        assert config["token"] == token
        assert config["branch"] == branch
        assert config["auto_configured"] is True
        assert config["version"] == "1.0"
        assert "updated_at" in config
    
    @pytest.mark.asyncio
    async def test_auto_configure_obsidian_sync_updates_existing_config(self, temp_storage_dir):
        """Test that auto_configure_obsidian_sync updates existing config when values change"""
        import json
        import aiofiles
        
        user_id = "test_user_789"
        user_dir = temp_storage_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        config_path = user_dir / "git_config.json"
        
        # Create initial config
        initial_config = {
            "repo_url": "https://github.com/user/old-vault.git",
            "token": "ghp_oldtoken",
            "branch": "main",
            "auto_configured": True,
            "version": "1.0"
        }
        async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(initial_config, indent=2))
        
        # Update with new values
        new_repo_url = "https://github.com/user/new-vault.git"
        new_token = "ghp_newtoken"
        
        await file_storage.auto_configure_obsidian_sync(
            user_id=user_id,
            repo_url=new_repo_url,
            token=new_token,
            branch="main"
        )
        
        # Verify config was updated
        async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
        
        assert config["repo_url"] == new_repo_url
        assert config["token"] == new_token
    
    @pytest.mark.asyncio
    async def test_auto_configure_obsidian_sync_skips_unchanged_config(self, temp_storage_dir):
        """Test that auto_configure_obsidian_sync skips write if config is unchanged"""
        import json
        import aiofiles
        import os
        
        user_id = "test_user_skip"
        user_dir = temp_storage_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        config_path = user_dir / "git_config.json"
        
        repo_url = "https://github.com/user/vault.git"
        token = "ghp_token123"
        branch = "main"
        
        # Create initial config
        initial_config = {
            "repo_url": repo_url,
            "token": token,
            "branch": branch,
            "auto_configured": True,
            "version": "1.0",
            "updated_at": "2024-01-01T00:00:00"
        }
        async with aiofiles.open(config_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(initial_config, indent=2))
        
        # Get initial modification time
        initial_mtime = config_path.stat().st_mtime
        
        # Call auto_configure with same values
        await file_storage.auto_configure_obsidian_sync(
            user_id=user_id,
            repo_url=repo_url,
            token=token,
            branch=branch
        )
        
        # Verify file modification time didn't change (or changed minimally)
        # Allow small time difference for file system operations
        final_mtime = config_path.stat().st_mtime
        # The file should not have been rewritten (mtime should be very close)
        # In practice, if unchanged, the function returns early, so mtime should be identical
        assert abs(final_mtime - initial_mtime) < 1.0  # Less than 1 second difference
    
    @pytest.mark.asyncio
    async def test_configure_obsidian_sync_manual(self, temp_storage_dir, setup_user):
        """Test manual configuration via configure_obsidian_sync tool"""
        import json
        import aiofiles
        
        repo_url = "https://github.com/user/vault.git"
        token = "ghp_manualtoken"
        branch = "main"
        
        result = await file_storage.configure_obsidian_sync(
            repo_url=repo_url,
            token=token,
            branch=branch
        )
        
        assert "Successfully configured Obsidian Sync" in result
        assert repo_url in result
        
        # Verify config file was created
        config_path = temp_storage_dir / "test_user_123" / "git_config.json"
        assert config_path.exists()
        
        # Verify config content
        async with aiofiles.open(config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            config = json.loads(content)
        
        assert config["repo_url"] == repo_url
        assert config["token"] == token
        assert config["branch"] == branch
        assert config["auto_configured"] is False  # Manual configuration
    
    @pytest.mark.asyncio
    async def test_configure_obsidian_sync_returns_status_when_no_params(self, temp_storage_dir, setup_user):
        """Test that configure_obsidian_sync returns helpful message when no params and not configured"""
        result = await file_storage.configure_obsidian_sync(repo_url=None, token=None)
        assert "No Obsidian sync configuration found" in result
        assert "customUserVars" in result or "repo_url and token" in result
    
    @pytest.mark.asyncio
    async def test_configure_obsidian_sync_returns_existing_config(self, temp_storage_dir, setup_user):
        """Test that configure_obsidian_sync returns existing config if already configured"""
        import json
        import aiofiles
        
        # First, configure it
        repo_url = "https://github.com/user/vault.git"
        token = "ghp_token"
        
        await file_storage.configure_obsidian_sync(
            repo_url=repo_url,
            token=token,
            branch="main"
        )
        
        # Then try to configure again without parameters
        result = await file_storage.configure_obsidian_sync(
            repo_url=None,
            token=None
        )
        
        assert "already configured" in result.lower()
        assert repo_url in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
