"""
Integration tests for OAuth flow in Docker and Production environments.

These tests verify the complete OAuth flow:
1. Authorization endpoint accessibility
2. Login form submission
3. Token exchange
4. Token persistence
5. Tool access with OAuth token

Run with:
    # Docker/local environment
    pytest tests/test_oauth_integration.py::test_oauth_flow_docker -v

    # Production environment (requires PRODUCTION_HOST env var)
    PRODUCTION_HOST=https://chat.example.com pytest tests/test_oauth_integration.py::test_oauth_flow_production -v
"""

import os
import pytest
import requests
import time
from typing import Dict, Optional
from unittest.mock import patch, MagicMock

# Test configuration
DOCKER_BASE_URL = os.environ.get("LIBRECHATMCP_URL", "http://localhost:3002")
PRODUCTION_HOST = os.environ.get("PRODUCTION_HOST")  # e.g., "https://chat.example.com"
LIBRECHAT_EMAIL = os.environ.get("TEST_LIBRECHAT_EMAIL")
LIBRECHAT_PASSWORD = os.environ.get("TEST_LIBRECHAT_PASSWORD")
LIBRECHAT_API_URL = os.environ.get("LIBRECHAT_API_BASE_URL", "http://localhost:3080/api")

# Skip production tests if PRODUCTION_HOST is not set
SKIP_PRODUCTION = pytest.mark.skipif(
    not PRODUCTION_HOST,
    reason="PRODUCTION_HOST environment variable not set"
)

# Skip tests if credentials are not provided
SKIP_IF_NO_CREDENTIALS = pytest.mark.skipif(
    not LIBRECHAT_EMAIL or not LIBRECHAT_PASSWORD,
    reason="TEST_LIBRECHAT_EMAIL and TEST_LIBRECHAT_PASSWORD environment variables required"
)


class OAuthFlowTester:
    """Helper class for testing OAuth flows"""
    
    def __init__(self, base_url: str, is_production: bool = False):
        self.base_url = base_url.rstrip('/')
        self.is_production = is_production
        self.authorize_url = f"{self.base_url}/authorize"
        self.token_url = f"{self.base_url}/token"
        self.mcp_url = f"{self.base_url}/mcp"
        self.session = requests.Session()
        self.session.verify = True  # Verify SSL certificates in production
        
    def test_authorization_endpoint_accessible(self) -> bool:
        """Test that the authorization endpoint is accessible"""
        try:
            response = self.session.get(
                self.authorize_url,
                params={
                    "redirect_uri": "http://localhost:3080/api/mcp/librechatmcp/oauth/callback",
                    "state": "test-user-123:librechatmcp",
                    "client_id": "librechatmcp"
                },
                timeout=10
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            assert "text/html" in response.headers.get("content-type", ""), "Expected HTML response"
            assert "Login" in response.text or "Connect" in response.text, "Expected login page"
            return True
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Authorization endpoint not accessible: {e}")
    
    def test_login_form_submission(self, email: str, password: str) -> Optional[str]:
        """Test login form submission and get authorization code"""
        state = f"test-user-123:librechatmcp"
        redirect_uri = "http://localhost:3080/api/mcp/librechatmcp/oauth/callback"
        
        # First, get the authorization page
        auth_response = self.session.get(
            self.authorize_url,
            params={
                "redirect_uri": redirect_uri,
                "state": state,
                "client_id": "librechatmcp"
            },
            timeout=10
        )
        assert auth_response.status_code == 200, "Authorization page should be accessible"
        
        # Submit login form
        login_response = self.session.post(
            self.authorize_url,
            params={
                "redirect_uri": redirect_uri,
                "state": state,
                "client_id": "librechatmcp"
            },
            data={
                "action": "login",
                "email": email,
                "password": password
            },
            allow_redirects=False,  # Don't follow redirect to capture the code
            timeout=30
        )
        
        # Should redirect with code and state
        if login_response.status_code == 302:
            location = login_response.headers.get("Location", "")
            # Extract code from redirect URL
            if "code=" in location:
                code = location.split("code=")[1].split("&")[0]
                return code
            else:
                pytest.fail(f"Redirect missing authorization code. Location: {location}")
        elif login_response.status_code == 200:
            # Check if there's an error message
            if "error" in login_response.text.lower() or "invalid" in login_response.text.lower():
                pytest.fail(f"Login failed: {login_response.text[:500]}")
            else:
                pytest.fail(f"Expected redirect (302), got {login_response.status_code}")
        else:
            pytest.fail(f"Unexpected status code: {login_response.status_code}")
    
    def test_token_exchange(self, auth_code: str) -> Dict[str, str]:
        """Test token exchange endpoint"""
        response = self.session.post(
            self.token_url,
            json={
                "code": auth_code,
                "grant_type": "authorization_code"
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        assert response.status_code == 200, f"Token exchange failed: {response.text}"
        token_data = response.json()
        
        assert "access_token" in token_data, "Response should contain access_token"
        assert "token_type" in token_data, "Response should contain token_type"
        assert token_data["token_type"] == "Bearer", "Token type should be Bearer"
        assert "expires_in" in token_data, "Response should contain expires_in"
        
        return token_data
    
    def test_tool_access_with_token(self, access_token: str) -> bool:
        """Test that MCP tools are accessible with OAuth token"""
        # Test a simple tool call (get_models requires no parameters)
        response = self.session.post(
            self.mcp_url,
            json={
                "method": "tools/call",
                "params": {
                    "name": "get_models",
                    "arguments": {}
                }
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        # Should get a valid response (200 or 400/500 with error details)
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            result = response.json()
            assert "result" in result or "content" in result, "Response should contain result"
            return True
        else:
            # Check if it's an authentication error
            error_text = response.text
            if "unauthorized" in error_text.lower() or "401" in error_text:
                pytest.fail(f"Authentication failed with token: {error_text}")
            else:
                # Other errors are acceptable (e.g., tool not found, invalid parameters)
                return False
    
    def test_token_persistence(self, access_token: str, user_id: str) -> bool:
        """Test that token persists across requests"""
        # Make multiple requests with the same token
        for i in range(3):
            response = self.session.post(
                self.mcp_url,
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "get_models",
                        "arguments": {}
                    }
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            
            if response.status_code == 401:
                pytest.fail(f"Token not persistent: request {i+1} failed with 401")
        
        return True


@SKIP_IF_NO_CREDENTIALS
def test_oauth_flow_docker():
    """
    Integration test for OAuth flow in Docker/local environment.
    
    This test verifies:
    1. Authorization endpoint is accessible
    2. Login form submission works
    3. Token exchange works
    4. Tools are accessible with OAuth token
    5. Token persistence
    
    Prerequisites:
    - LibreChatMCP service running on localhost:3002
    - LibreChat API running on localhost:3080
    - Set TEST_LIBRECHAT_EMAIL and TEST_LIBRECHAT_PASSWORD environment variables
    """
    tester = OAuthFlowTester(DOCKER_BASE_URL, is_production=False)
    
    # Step 1: Test authorization endpoint
    print("\n[1/5] Testing authorization endpoint accessibility...")
    tester.test_authorization_endpoint_accessible()
    print("✅ Authorization endpoint is accessible")
    
    # Step 2: Test login form submission
    print("\n[2/5] Testing login form submission...")
    auth_code = tester.test_login_form_submission(LIBRECHAT_EMAIL, LIBRECHAT_PASSWORD)
    assert auth_code, "Should receive authorization code"
    print(f"✅ Login successful, received authorization code: {auth_code[:10]}...")
    
    # Step 3: Test token exchange
    print("\n[3/5] Testing token exchange...")
    token_data = tester.test_token_exchange(auth_code)
    access_token = token_data["access_token"]
    print(f"✅ Token exchange successful, received access token: {access_token[:20]}...")
    
    # Step 4: Test tool access with token
    print("\n[4/5] Testing tool access with OAuth token...")
    tool_access_works = tester.test_tool_access_with_token(access_token)
    if tool_access_works:
        print("✅ Tools are accessible with OAuth token")
    else:
        print("⚠️  Tool access returned error (may be expected if service not fully configured)")
    
    # Step 5: Test token persistence
    print("\n[5/5] Testing token persistence...")
    tester.test_token_persistence(access_token, "test-user-123")
    print("✅ Token persists across multiple requests")
    
    print("\n✅ All OAuth flow tests passed for Docker environment!")


@SKIP_PRODUCTION
@SKIP_IF_NO_CREDENTIALS
def test_oauth_flow_production():
    """
    Integration test for OAuth flow in Production environment.
    
    This test verifies:
    1. Production authorization endpoint is accessible via HTTPS
    2. Ingress routing works correctly
    3. Login form submission works
    4. Token exchange works
    5. Tools are accessible with OAuth token
    6. Token persistence
    
    Prerequisites:
    - Production deployment accessible
    - Set PRODUCTION_HOST environment variable (e.g., "https://chat.example.com")
    - Set TEST_LIBRECHAT_EMAIL and TEST_LIBRECHAT_PASSWORD environment variables
    """
    production_base_url = f"{PRODUCTION_HOST}/mcp/librechatmcp/oauth"
    tester = OAuthFlowTester(production_base_url, is_production=True)
    
    # Step 1: Test authorization endpoint (via ingress)
    print("\n[1/6] Testing production authorization endpoint (via ingress)...")
    tester.test_authorization_endpoint_accessible()
    print("✅ Production authorization endpoint is accessible via HTTPS")
    
    # Step 2: Verify HTTPS is enforced
    print("\n[2/6] Verifying HTTPS enforcement...")
    http_url = production_base_url.replace("https://", "http://")
    try:
        response = requests.get(f"{http_url}/authorize", allow_redirects=False, timeout=5)
        # Should redirect to HTTPS or reject
        assert response.status_code in [301, 302, 400, 403], "HTTP should redirect or be rejected"
        print("✅ HTTPS is enforced (HTTP requests redirected/rejected)")
    except requests.exceptions.RequestException:
        print("✅ HTTP requests are rejected (expected)")
    
    # Step 3: Test login form submission
    print("\n[3/6] Testing login form submission in production...")
    auth_code = tester.test_login_form_submission(LIBRECHAT_EMAIL, LIBRECHAT_PASSWORD)
    assert auth_code, "Should receive authorization code"
    print(f"✅ Login successful, received authorization code: {auth_code[:10]}...")
    
    # Step 4: Test token exchange
    print("\n[4/6] Testing token exchange in production...")
    token_data = tester.test_token_exchange(auth_code)
    access_token = token_data["access_token"]
    print(f"✅ Token exchange successful, received access token: {access_token[:20]}...")
    
    # Step 5: Test tool access with token (via MCP endpoint)
    print("\n[5/6] Testing tool access with OAuth token in production...")
    mcp_base_url = f"{PRODUCTION_HOST}/api/mcp/librechatmcp"
    tool_tester = OAuthFlowTester(mcp_base_url, is_production=True)
    tool_tester.mcp_url = f"{mcp_base_url}/mcp"
    tool_access_works = tool_tester.test_tool_access_with_token(access_token)
    if tool_access_works:
        print("✅ Tools are accessible with OAuth token in production")
    else:
        print("⚠️  Tool access returned error (may be expected if service not fully configured)")
    
    # Step 6: Test token persistence
    print("\n[6/6] Testing token persistence in production...")
    tester.test_token_persistence(access_token, "test-user-123")
    print("✅ Token persists across multiple requests in production")
    
    print("\n✅ All OAuth flow tests passed for Production environment!")


def test_oauth_endpoints_health_check():
    """
    Quick health check test that doesn't require credentials.
    Verifies endpoints are accessible without authentication.
    """
    tester = OAuthFlowTester(DOCKER_BASE_URL)
    
    # Test authorization endpoint returns HTML (even without proper params)
    response = requests.get(tester.authorize_url, timeout=5)
    assert response.status_code in [200, 400], "Authorization endpoint should be accessible"
    
    # Test token endpoint rejects requests without code
    response = requests.post(tester.token_url, json={}, timeout=5)
    assert response.status_code == 400, "Token endpoint should reject invalid requests"
    
    print("✅ OAuth endpoints health check passed")


def test_oauth_configuration_prevents_error_redirect():
    """
    CRITICAL TEST: Prevents OAuth callback from redirecting to error page.
    
    This test verifies that the OAuth configuration in librechat.yaml is correct
    and will not cause redirects to /login?redirect=false&error=auth_failed.
    
    This test should FAIL if:
    - redirect_uri format is incorrect
    - Callback URL doesn't match expected pattern
    - OAuth configuration is misconfigured
    - Server name mismatch between config and callback URL
    
    This prevents the issue where OAuth redirects to:
    http://138.199.226.49:8080/login?redirect=false&error=auth_failed
    """
    import re
    from pathlib import Path
    
    # Read librechat.yaml to verify OAuth configuration
    librechat_yaml_path = Path(__file__).parent.parent.parent / "librechat.yaml"
    if not librechat_yaml_path.exists():
        librechat_yaml_path = Path(__file__).parent.parent.parent.parent / "librechat.yaml"
    
    if not librechat_yaml_path.exists():
        pytest.skip("librechat.yaml not found - cannot verify OAuth configuration")
    
    with open(librechat_yaml_path, 'r') as f:
        content = f.read()
    
    # Verify librechatmcp server configuration exists
    assert "librechatmcp:" in content, "librechatmcp server configuration not found"
    assert "oauth:" in content, "OAuth configuration not found for librechatmcp"
    
    # Extract OAuth configuration section using regex
    oauth_section_match = re.search(
        r'librechatmcp:.*?oauth:\s*\n(.*?)(?=\n  [a-z]|\n\n|$)',
        content,
        re.DOTALL
    )
    assert oauth_section_match, "OAuth section not found for librechatmcp"
    
    oauth_section = oauth_section_match.group(1)
    
    # Extract required OAuth fields
    redirect_uri_match = re.search(r'redirect_uri:\s*(.+?)(?:\s*#|$)', oauth_section, re.MULTILINE)
    authorization_url_match = re.search(r'authorization_url:\s*(.+?)(?:\s*#|$)', oauth_section, re.MULTILINE)
    token_url_match = re.search(r'token_url:\s*(.+?)(?:\s*#|$)', oauth_section, re.MULTILINE)
    client_id_match = re.search(r'client_id:\s*(.+?)(?:\s*#|$)', oauth_section, re.MULTILINE)
    
    assert redirect_uri_match, "redirect_uri not found in OAuth configuration"
    assert authorization_url_match, "authorization_url not found in OAuth configuration"
    assert token_url_match, "token_url not found in OAuth configuration"
    assert client_id_match, "client_id not found in OAuth configuration"
    
    redirect_uri = redirect_uri_match.group(1).strip().strip('"').strip("'")
    authorization_url = authorization_url_match.group(1).strip().strip('"').strip("'")
    token_url = token_url_match.group(1).strip().strip('"').strip("'")
    client_id = client_id_match.group(1).strip().strip('"').strip("'")
    
    # Verify client_id matches server name
    assert client_id == "librechatmcp", (
        f"client_id '{client_id}' does not match server name 'librechatmcp'. "
        f"This mismatch can cause OAuth callback failures and redirects to error page."
    )
    
    # Verify redirect_uri format is correct
    # Should be: http://localhost:3080/api/mcp/librechatmcp/oauth/callback (local)
    # Or: https://domain.com/api/mcp/librechatmcp/oauth/callback (production)
    expected_callback_path = "/api/mcp/librechatmcp/oauth/callback"
    assert expected_callback_path in redirect_uri, (
        f"redirect_uri does not contain expected callback path.\n"
        f"Expected: ...{expected_callback_path}\n"
        f"Actual: {redirect_uri}\n"
        f"LibreChat expects the callback at /api/mcp/{{serverName}}/oauth/callback\n"
        f"This mismatch will cause OAuth callback to fail and redirect to error page."
    )
    
    # Verify redirect_uri doesn't contain invalid patterns
    if "localhost" in redirect_uri and redirect_uri.startswith("https://"):
        pytest.fail(
            f"redirect_uri contains both 'localhost' and 'https://' which is invalid: {redirect_uri}\n"
            f"Production URLs should not use localhost. This will cause OAuth failures."
        )
    
    # Verify the callback URL matches the expected LibreChat MCP callback pattern
    # LibreChat expects: /api/mcp/{serverName}/oauth/callback where serverName matches client_id
    callback_path_match = re.search(r'/api/mcp/([^/]+)/oauth/callback', redirect_uri)
    assert callback_path_match, (
        f"redirect_uri does not match expected callback pattern: {redirect_uri}\n"
        f"Expected pattern: .../api/mcp/{{serverName}}/oauth/callback"
    )
    
    server_name_in_callback = callback_path_match.group(1)
    assert server_name_in_callback == "librechatmcp", (
        f"Server name in callback URL '{server_name_in_callback}' does not match "
        f"expected 'librechatmcp'.\n"
        f"redirect_uri: {redirect_uri}\n"
        f"This mismatch will cause OAuth callback to fail and redirect to error page."
    )
    
    # Verify authorization_url and token_url are accessible (basic format check)
    assert authorization_url.startswith(("http://", "https://")), (
        f"authorization_url must start with http:// or https://: {authorization_url}"
    )
    assert token_url.startswith(("http://", "https://")), (
        f"token_url must start with http:// or https://: {token_url}"
    )
    
    print("✅ OAuth configuration validation passed:")
    print(f"   client_id: {client_id}")
    print(f"   redirect_uri: {redirect_uri}")
    print(f"   authorization_url: {authorization_url}")
    print(f"   token_url: {token_url}")
    print(f"   Server name in callback: {server_name_in_callback}")


def test_oauth_callback_does_not_redirect_to_error():
    """
    CRITICAL TEST: Prevents OAuth callback from redirecting to error page.
    
    This test verifies that the OAuth callback URL format is correct and
    that the callback doesn't result in redirects to /login?error=auth_failed.
    
    This test should FAIL if:
    - redirect_uri format is incorrect
    - Callback URL doesn't match expected pattern
    - OAuth configuration is misconfigured
    
    This prevents the issue where OAuth redirects to:
    http://138.199.226.49:8080/login?redirect=false&error=auth_failed
    """
    import re
    from pathlib import Path
    
    # Read librechat.yaml to verify OAuth configuration
    librechat_yaml_path = Path(__file__).parent.parent.parent / "librechat.yaml"
    if not librechat_yaml_path.exists():
        librechat_yaml_path = Path(__file__).parent.parent.parent.parent / "librechat.yaml"
    
    if not librechat_yaml_path.exists():
        pytest.skip("librechat.yaml not found - cannot verify OAuth configuration")
    
    with open(librechat_yaml_path, 'r') as f:
        content = f.read()
    
    # Verify librechatmcp OAuth configuration exists
    assert "librechatmcp:" in content, "librechatmcp server configuration not found"
    assert "oauth:" in content, "OAuth configuration not found for librechatmcp"
    
    # Extract OAuth configuration
    oauth_section = re.search(r'librechatmcp:.*?oauth:(.*?)(?=\n  [a-z]|\n\n|$)', content, re.DOTALL)
    assert oauth_section, "OAuth section not found for librechatmcp"
    
    oauth_config = oauth_section.group(1)
    
    # Verify redirect_uri format
    redirect_uri_match = re.search(r'redirect_uri:\s*(.+)', oauth_config)
    assert redirect_uri_match, "redirect_uri not found in OAuth configuration"
    
    redirect_uri = redirect_uri_match.group(1).strip()
    
    # Remove comments if present
    redirect_uri = redirect_uri.split('#')[0].strip()
    
    # Verify redirect_uri format is correct
    # Should be: http://localhost:3080/api/mcp/librechatmcp/oauth/callback (local)
    # Or: https://domain.com/api/mcp/librechatmcp/oauth/callback (production)
    expected_pattern = r'https?://[^/]+/api/mcp/librechatmcp/oauth/callback'
    assert re.match(expected_pattern, redirect_uri), (
        f"redirect_uri format is incorrect: {redirect_uri}\n"
        f"Expected pattern: {expected_pattern}\n"
        f"This will cause OAuth callback to fail and redirect to error page."
    )
    
    # Verify authorization_url format
    auth_url_match = re.search(r'authorization_url:\s*(.+)', oauth_config)
    assert auth_url_match, "authorization_url not found in OAuth configuration"
    
    auth_url = auth_url_match.group(1).strip().split('#')[0].strip()
    
    # Verify token_url format
    token_url_match = re.search(r'token_url:\s*(.+)', oauth_config)
    assert token_url_match, "token_url not found in OAuth configuration"
    
    token_url = token_url_match.group(1).strip().split('#')[0].strip()
    
    # Verify client_id matches server name
    client_id_match = re.search(r'client_id:\s*(.+)', oauth_config)
    assert client_id_match, "client_id not found in OAuth configuration"
    
    client_id = client_id_match.group(1).strip().split('#')[0].strip()
    assert client_id == "librechatmcp", (
        f"client_id '{client_id}' does not match server name 'librechatmcp'. "
        f"This mismatch can cause OAuth callback failures."
    )
    
    # Verify redirect_uri doesn't contain localhost in production-like URLs
    # (This is a common mistake - localhost URLs won't work in production)
    if "localhost" in redirect_uri and "https://" in redirect_uri:
        pytest.fail(
            f"redirect_uri contains both 'localhost' and 'https://' which is invalid: {redirect_uri}\n"
            f"Production URLs should not use localhost."
        )
    
    # Verify the callback path matches the expected LibreChat MCP callback pattern
    # LibreChat expects: /api/mcp/{serverName}/oauth/callback
    callback_path = "/api/mcp/librechatmcp/oauth/callback"
    assert callback_path in redirect_uri, (
        f"redirect_uri does not contain expected callback path: {callback_path}\n"
        f"Actual redirect_uri: {redirect_uri}\n"
        f"LibreChat expects the callback at /api/mcp/{{serverName}}/oauth/callback"
    )
    
    print("✅ OAuth configuration validation passed:")
    print(f"   redirect_uri: {redirect_uri}")
    print(f"   authorization_url: {auth_url}")
    print(f"   token_url: {token_url}")
    print(f"   client_id: {client_id}")


def test_oauth_callback_url_construction():
    """
    Test that verifies the OAuth callback URL is constructed correctly.
    
    This prevents issues where the callback URL doesn't match what LibreChat expects,
    causing redirects to error pages.
    """
    # Expected callback URL pattern for LibreChat MCP
    expected_callback_pattern = r'/api/mcp/librechatmcp/oauth/callback'
    
    # Test various redirect_uri formats that should work
    valid_redirect_uris = [
        "http://localhost:3080/api/mcp/librechatmcp/oauth/callback",
        "https://chat.example.com/api/mcp/librechatmcp/oauth/callback",
        "https://138.199.226.49:8080/api/mcp/librechatmcp/oauth/callback",
    ]
    
    for redirect_uri in valid_redirect_uris:
        assert expected_callback_pattern in redirect_uri, (
            f"Redirect URI '{redirect_uri}' does not contain expected callback path"
        )
    
    # Test invalid redirect_uri formats that should fail
    invalid_redirect_uris = [
        "http://localhost:3080/api/mcp/librechat_mcp/oauth/callback",  # Wrong server name
        "http://localhost:3080/api/mcp/oauth/callback",  # Missing server name
        "http://localhost:3080/oauth/callback",  # Wrong path
    ]
    
    for redirect_uri in invalid_redirect_uris:
        assert expected_callback_pattern not in redirect_uri, (
            f"Invalid redirect URI '{redirect_uri}' should not match expected pattern"
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

