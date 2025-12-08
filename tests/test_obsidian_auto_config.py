#!/usr/bin/env python3
"""
Test script for Obsidian Sync Auto-Configuration

This script tests the auto-configuration functionality by simulating
HTTP requests with headers containing Obsidian sync credentials.

Usage:
    python test_obsidian_auto_config.py

Requirements:
    - Docker Compose services running (librechatmcp)
    - Or run locally: cd LibreChatMCP && python -m uvicorn main:app --port 3002
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
MCP_SERVER_URL = "http://localhost:3002/mcp"
TEST_USER_ID = "test_user_auto_config"
TEST_REPO_URL = "https://github.com/testuser/test-vault.git"
TEST_TOKEN = "ghp_testtoken123456"
TEST_BRANCH = "main"

# Storage path (adjust if different)
STORAGE_ROOT = Path("./data/user-files")


def test_auto_configuration():
    """Test that auto-configuration creates git_config.json when headers are present"""
    print("=" * 60)
    print("Testing Obsidian Sync Auto-Configuration")
    print("=" * 60)
    
    # Test 1: Call MCP tool with Obsidian headers
    print("\n[Test 1] Calling MCP tool with Obsidian sync headers...")
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-User-ID": TEST_USER_ID,
        "X-Obsidian-Repo-URL": TEST_REPO_URL,
        "X-Obsidian-Token": TEST_TOKEN,
        "X-Obsidian-Branch": TEST_BRANCH,
    }
    
    # Call list_files tool to trigger middleware
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "list_files",
            "arguments": {}
        },
        "id": 1
    }
    
    try:
        response = requests.post(
            MCP_SERVER_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print(f"✅ MCP tool call successful (status {response.status_code})")
        
        # Wait a moment for async operations
        time.sleep(1)
        
        # Test 2: Verify config file was created
        print("\n[Test 2] Verifying git_config.json was created...")
        
        config_path = STORAGE_ROOT / TEST_USER_ID / "git_config.json"
        
        if not config_path.exists():
            print(f"❌ Config file not found at {config_path}")
            print(f"   Storage root: {STORAGE_ROOT.absolute()}")
            print(f"   User directory exists: {(STORAGE_ROOT / TEST_USER_ID).exists()}")
            if (STORAGE_ROOT / TEST_USER_ID).exists():
                print(f"   Files in user directory: {list((STORAGE_ROOT / TEST_USER_ID).iterdir())}")
            return False
        
        print(f"✅ Config file found at {config_path}")
        
        # Test 3: Verify config content
        print("\n[Test 3] Verifying config file content...")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        checks = [
            (config.get("repo_url") == TEST_REPO_URL, "repo_url", config.get("repo_url")),
            (config.get("token") == TEST_TOKEN, "token", "***hidden***"),
            (config.get("branch") == TEST_BRANCH, "branch", config.get("branch")),
            (config.get("auto_configured") is True, "auto_configured flag", config.get("auto_configured")),
            ("updated_at" in config, "updated_at timestamp", config.get("updated_at", "missing")),
            (config.get("version") == "1.0", "version", config.get("version")),
        ]
        
        all_passed = True
        for passed, field, value in checks:
            if passed:
                print(f"   ✅ {field}: {value}")
            else:
                print(f"   ❌ {field}: Expected value not found (got: {value})")
                all_passed = False
        
        if not all_passed:
            print(f"\n   Full config: {json.dumps(config, indent=2)}")
            return False
        
        print("\n✅ All configuration checks passed!")
        
        # Test 4: Test that second call doesn't overwrite (rate limiting)
        print("\n[Test 4] Testing rate limiting (should not overwrite immediately)...")
        
        # Get original updated_at
        original_updated_at = config.get("updated_at")
        
        # Call again immediately
        response2 = requests.post(
            MCP_SERVER_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        time.sleep(0.5)
        
        # Read config again
        with open(config_path, 'r') as f:
            config2 = json.load(f)
        
        if config2.get("updated_at") == original_updated_at:
            print("✅ Rate limiting working - config not overwritten immediately")
        else:
            print("⚠️  Config was updated (rate limiting may not be active or cooldown passed)")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to MCP server at {MCP_SERVER_URL}")
        print("   Make sure the librechatmcp service is running:")
        print("   - docker-compose up -d librechatmcp")
        print("   - Or run locally: cd LibreChatMCP && python -m uvicorn main:app --port 3002")
        return False
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_configuration():
    """Test manual configuration via configure_obsidian_sync tool"""
    print("\n" + "=" * 60)
    print("Testing Manual Configuration (configure_obsidian_sync tool)")
    print("=" * 60)
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-User-ID": f"{TEST_USER_ID}_manual",
    }
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "configure_obsidian_sync",
            "arguments": {
                "repo_url": TEST_REPO_URL,
                "token": TEST_TOKEN,
                "branch": TEST_BRANCH
            }
        },
        "id": 2
    }
    
    try:
        response = requests.post(
            MCP_SERVER_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Handle streaming response (text/event-stream)
        if 'text/event-stream' in response.headers.get('Content-Type', ''):
            # Parse SSE format
            lines = response.text.split('\n')
            result_content = None
            for line in lines:
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        if 'result' in data:
                            result_content = data['result']
                            break
                    except:
                        pass
            if result_content:
                print(f"✅ Tool call successful")
                print(f"   Result: {result_content.get('content', 'N/A')}")
            else:
                print(f"✅ Tool call successful (streaming response)")
        else:
            try:
                result = response.json()
                print(f"✅ Tool call successful")
                print(f"   Result: {result.get('result', {}).get('content', 'N/A')}")
            except:
                print(f"✅ Tool call successful (non-JSON response)")
                print(f"   Response: {response.text[:200]}")
        
        # Verify config was created
        config_path = STORAGE_ROOT / f"{TEST_USER_ID}_manual" / "git_config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            if config.get("auto_configured") is False:
                print("✅ Manual configuration flag set correctly")
                return True
            else:
                print("❌ Manual configuration flag incorrect")
                return False
        else:
            print("❌ Config file not created")
            return False
            
    except Exception as e:
        print(f"❌ Error during manual configuration test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Obsidian Sync Auto-Configuration Test Suite")
    print("=" * 60)
    print(f"\nMCP Server: {MCP_SERVER_URL}")
    print(f"Storage Root: {STORAGE_ROOT.absolute()}")
    print(f"Test User ID: {TEST_USER_ID}")
    print()
    
    # Create storage directory if it doesn't exist
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Run tests
    test1_passed = test_auto_configuration()
    test2_passed = test_manual_configuration()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Auto-configuration test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Manual configuration test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
