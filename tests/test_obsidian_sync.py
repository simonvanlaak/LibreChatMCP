#!/usr/bin/env python3
"""
Test script for Obsidian sync auto-configuration
Simulates a request with customUserVars headers
"""
import requests
import json
import time

MCP_SERVER_URL = "http://localhost:3002/mcp"

# Test user ID
TEST_USER_ID = "test-user-123"

# Test Obsidian sync credentials
TEST_REPO_URL = "https://github.com/testuser/test-vault.git"
TEST_TOKEN = "ghp_test_token_1234567890abcdef"
TEST_BRANCH = "main"

def test_auto_configuration():
    """Test that auto-configuration works when headers are present"""
    print("Testing Obsidian sync auto-configuration...")
    print(f"MCP Server: {MCP_SERVER_URL}")
    print(f"User ID: {TEST_USER_ID}")
    print(f"Repo URL: {TEST_REPO_URL}")
    print()
    
    # Create a simple MCP initialize request
    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": 1
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": TEST_USER_ID,
        "X-Obsidian-Repo-URL": TEST_REPO_URL,
        "X-Obsidian-Token": TEST_TOKEN,
        "X-Obsidian-Branch": TEST_BRANCH
    }
    
    print("Sending request with Obsidian sync headers...")
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Response Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ Request successful!")
        else:
            print(f"⚠️ Request returned status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Wait a moment for async operations
    time.sleep(2)
    
    # Check if config file was created
    import os
    config_path = f"./data/user-files/{TEST_USER_ID}/git_config.json"
    print(f"\nChecking for config file at: {config_path}")
    
    if os.path.exists(config_path):
        print("✅ Config file created!")
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"Config contents:")
        print(f"  Repo URL: {config.get('repo_url', 'N/A')}")
        print(f"  Branch: {config.get('branch', 'N/A')}")
        print(f"  Auto-configured: {config.get('auto_configured', False)}")
        print(f"  Updated at: {config.get('updated_at', 'N/A')}")
        
        # Verify values match
        if (config.get('repo_url') == TEST_REPO_URL and
            config.get('token') == TEST_TOKEN and
            config.get('branch') == TEST_BRANCH):
            print("✅ Config values match expected values!")
            return True
        else:
            print("⚠️ Config values don't match!")
            return False
    else:
        print("❌ Config file not found!")
        return False

def test_manual_configure_obsidian_sync():
    """Test manual call to configure_obsidian_sync tool with proper headers"""
    print("\n" + "="*60)
    print("Testing manual configure_obsidian_sync tool call...")
    print("="*60)
    
    # Test 1: With X-User-ID header (should work)
    print("\nTest 1: Calling configure_obsidian_sync WITH X-User-ID header")
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
    
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": TEST_USER_ID,  # Required!
    }
    
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Response Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200 and "error" not in result:
            print("✅ Manual tool call successful with X-User-ID header!")
            return True
        else:
            print(f"⚠️ Request returned error: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 2: Without X-User-ID header (should fail)
    print("\nTest 2: Calling configure_obsidian_sync WITHOUT X-User-ID header (should fail)")
    headers_no_user = {
        "Content-Type": "application/json",
        # Missing X-User-ID header
    }
    
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json=payload,
            headers=headers_no_user,
            timeout=10
        )
        print(f"Response Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if "error" in result and "User not authenticated" in str(result.get("error", {}).get("message", "")):
            print("✅ Correctly rejected request without X-User-ID header!")
            return True
        else:
            print("⚠️ Expected authentication error but got different response")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("="*60)
    print("Obsidian Sync Configuration Tests")
    print("="*60)
    
    # Test auto-configuration via middleware
    success1 = test_auto_configuration()
    
    # Test manual tool call
    success2 = test_manual_configure_obsidian_sync()
    
    print("\n" + "="*60)
    print("Test Summary:")
    print(f"  Auto-configuration: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"  Manual tool call: {'✅ PASS' if success2 else '❌ FAIL'}")
    print("="*60)
    
    exit(0 if (success1 and success2) else 1)

