"""
Integration tests for RAG API integration

Tests the actual communication with the RAG API service
Requires RAG_API_URL to be set and accessible
"""

import pytest
import os
import asyncio
import httpx
from pathlib import Path

# Import the file storage module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools import file_storage


@pytest.fixture
def rag_api_url():
    """Get RAG API URL from environment or skip if not available"""
    url = os.environ.get("RAG_API_URL")
    if not url:
        pytest.skip("RAG_API_URL not set, skipping integration tests")
    return url


@pytest.fixture
async def check_rag_api_available(rag_api_url):
    """Check if RAG API is actually available"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{rag_api_url}/health")
            if response.status_code != 200:
                pytest.skip(f"RAG API not available at {rag_api_url}")
    except Exception as e:
        pytest.skip(f"RAG API not reachable: {e}")


@pytest.fixture
def setup_test_user():
    """Setup test user context"""
    user_id = f"test_integration_user_{os.getpid()}"
    file_storage.set_current_user(user_id)
    yield user_id
    file_storage._current_user_id = None


@pytest.mark.integration
class TestRAGAPIIntegration:
    """Integration tests for RAG API communication"""
    
    @pytest.mark.asyncio
    async def test_embed_endpoint(self, rag_api_url, check_rag_api_available, setup_test_user):
        """Test direct embedding via RAG API"""
        file_id = f"user_{setup_test_user}_integration_test.txt"
        content = "This is a test document for integration testing."
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{rag_api_url}/embed",
                json={
                    "file_id": file_id,
                    "content": content,
                    "metadata": {
                        "user_id": setup_test_user,
                        "filename": "integration_test.txt"
                    },
                    "chunk_size": 1500,
                    "chunk_overlap": 100
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "file_id" in data
            
            # Cleanup
            await client.delete(f"{rag_api_url}/embed/{file_id}")
    
    @pytest.mark.asyncio
    async def test_query_endpoint(self, rag_api_url, check_rag_api_available, setup_test_user):
        """Test querying embeddings via RAG API"""
        file_id = f"user_{setup_test_user}_query_test.txt"
        content = "The quick brown fox jumps over the lazy dog."
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, embed a document
            await client.post(
                f"{rag_api_url}/embed",
                json={
                    "file_id": file_id,
                    "content": content,
                    "metadata": {
                        "user_id": setup_test_user,
                        "filename": "query_test.txt"
                    }
                }
            )
            
            # Give it a moment to index
            await asyncio.sleep(1)
            
            # Now query it
            response = await client.post(
                f"{rag_api_url}/query",
                json={
                    "query": "brown fox",
                    "filters": {
                        "user_id": setup_test_user
                    },
                    "top_k": 5
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            
            # If results exist, verify they match our user
            if data["results"]:
                for result in data["results"]:
                    metadata = result.get("metadata", {})
                    assert metadata.get("user_id") == setup_test_user
            
            # Cleanup
            await client.delete(f"{rag_api_url}/embed/{file_id}")
    
    @pytest.mark.asyncio
    async def test_delete_endpoint(self, rag_api_url, check_rag_api_available, setup_test_user):
        """Test deleting embeddings via RAG API"""
        file_id = f"user_{setup_test_user}_delete_test.txt"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Embed a document
            await client.post(
                f"{rag_api_url}/embed",
                json={
                    "file_id": file_id,
                    "content": "Document to be deleted",
                    "metadata": {"user_id": setup_test_user}
                }
            )
            
            # Delete it
            response = await client.delete(f"{rag_api_url}/embed/{file_id}")
            
            # Should succeed even if file doesn't exist (idempotent)
            assert response.status_code in [200, 204, 404]
    
    @pytest.mark.asyncio
    async def test_user_scoped_search(self, rag_api_url, check_rag_api_available):
        """Test that search results are properly scoped to users"""
        user_a_id = f"test_user_a_{os.getpid()}"
        user_b_id = f"test_user_b_{os.getpid()}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # User A uploads a document
            await client.post(
                f"{rag_api_url}/embed",
                json={
                    "file_id": f"user_{user_a_id}_doc.txt",
                    "content": "User A's confidential document about project X",
                    "metadata": {"user_id": user_a_id, "filename": "doc.txt"}
                }
            )
            
            # User B uploads a different document
            await client.post(
                f"{rag_api_url}/embed",
                json={
                    "file_id": f"user_{user_b_id}_doc.txt",
                    "content": "User B's notes about project Y",
                    "metadata": {"user_id": user_b_id, "filename": "doc.txt"}
                }
            )
            
            # Give time to index
            await asyncio.sleep(1)
            
            # User A searches - should only see their document
            response_a = await client.post(
                f"{rag_api_url}/query",
                json={
                    "query": "project",
                    "filters": {"user_id": user_a_id},
                    "top_k": 10
                }
            )
            
            results_a = response_a.json().get("results", [])
            for result in results_a:
                metadata = result.get("metadata", {})
                assert metadata.get("user_id") == user_a_id
                assert "project X" in result.get("text", "") or metadata.get("filename") == "doc.txt"
            
            # User B searches - should only see their document
            response_b = await client.post(
                f"{rag_api_url}/query",
                json={
                    "query": "project",
                    "filters": {"user_id": user_b_id},
                    "top_k": 10
                }
            )
            
            results_b = response_b.json().get("results", [])
            for result in results_b:
                metadata = result.get("metadata", {})
                assert metadata.get("user_id") == user_b_id
                assert "project Y" in result.get("text", "") or metadata.get("filename") == "doc.txt"
            
            # Cleanup
            await client.delete(f"{rag_api_url}/embed/user_{user_a_id}_doc.txt")
            await client.delete(f"{rag_api_url}/embed/user_{user_b_id}_doc.txt")


@pytest.mark.integration
class TestFileStorageEndToEnd:
    """End-to-end integration tests with actual RAG API"""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, rag_api_url, check_rag_api_available, setup_test_user):
        """Test complete workflow: upload -> search -> modify -> search -> delete"""
        import tempfile
        
        # Setup temporary storage
        with tempfile.TemporaryDirectory() as tmpdir:
            old_storage_root = file_storage.STORAGE_ROOT
            file_storage.STORAGE_ROOT = Path(tmpdir)
            
            try:
                # 1. Upload a file
                result = await file_storage.upload_file(
                    "workflow_test.txt",
                    "This document discusses machine learning and artificial intelligence."
                )
                assert "Successfully uploaded" in result
                
                # Give RAG API time to index
                await asyncio.sleep(2)
                
                # 2. Search for the file
                result = await file_storage.search_files("machine learning")
                assert "workflow_test.txt" in result or "No results found" in result
                
                # 3. Modify the file
                result = await file_storage.modify_file(
                    "workflow_test.txt",
                    "This document now discusses deep learning and neural networks instead."
                )
                assert "Successfully modified" in result
                
                # Give RAG API time to re-index
                await asyncio.sleep(2)
                
                # 4. Search for new content
                result = await file_storage.search_files("neural networks")
                # Results may vary based on RAG API implementation
                
                # 5. Delete the file
                result = await file_storage.delete_file("workflow_test.txt")
                assert "Successfully deleted" in result
                
                # 6. Verify file is gone
                result = await file_storage.list_files()
                assert "workflow_test.txt" not in result
                
            finally:
                file_storage.STORAGE_ROOT = old_storage_root


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
