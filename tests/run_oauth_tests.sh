#!/bin/bash
# Script to run OAuth integration tests for Docker and Production environments

set -e

echo "🔐 OAuth Integration Test Runner"
echo "================================"
echo ""

# Check for required environment variables
if [ -z "$TEST_LIBRECHAT_EMAIL" ] || [ -z "$TEST_LIBRECHAT_PASSWORD" ]; then
    echo "❌ ERROR: Required environment variables not set:"
    echo "   - TEST_LIBRECHAT_EMAIL"
    echo "   - TEST_LIBRECHAT_PASSWORD"
    echo ""
    echo "Usage:"
    echo "  export TEST_LIBRECHAT_EMAIL='your-email@example.com'"
    echo "  export TEST_LIBRECHAT_PASSWORD='your-password'"
    echo "  ./tests/run_oauth_tests.sh"
    exit 1
fi

# Default to Docker environment
ENVIRONMENT="${1:-docker}"

case "$ENVIRONMENT" in
    docker|local)
        echo "🐳 Testing OAuth flow in Docker/Local environment..."
        echo "   Base URL: ${LIBRECHATMCP_URL:-http://localhost:3002}"
        echo ""
        pytest tests/test_oauth_integration.py::test_oauth_flow_docker -v
        ;;
    
    production|prod)
        if [ -z "$PRODUCTION_HOST" ]; then
            echo "❌ ERROR: PRODUCTION_HOST environment variable required for production tests"
            echo "   Example: export PRODUCTION_HOST='https://chat.example.com'"
            exit 1
        fi
        echo "🚀 Testing OAuth flow in Production environment..."
        echo "   Production Host: $PRODUCTION_HOST"
        echo ""
        pytest tests/test_oauth_integration.py::test_oauth_flow_production -v
        ;;
    
    health)
        echo "🏥 Running OAuth endpoints health check (no credentials required)..."
        echo ""
        pytest tests/test_oauth_integration.py::test_oauth_endpoints_health_check -v
        ;;
    
    config)
        echo "🔍 Validating OAuth configuration (prevents error redirects)..."
        echo ""
        pytest tests/test_oauth_integration.py::test_oauth_configuration_prevents_error_redirect -v
        ;;
    
    all)
        echo "🧪 Running all OAuth integration tests..."
        echo ""
        echo "1️⃣  OAuth configuration validation (CRITICAL - prevents error redirects)..."
        pytest tests/test_oauth_integration.py::test_oauth_configuration_prevents_error_redirect -v
        echo ""
        echo "2️⃣  Health check (no credentials)..."
        pytest tests/test_oauth_integration.py::test_oauth_endpoints_health_check -v
        echo ""
        echo "3️⃣  Docker/Local environment..."
        pytest tests/test_oauth_integration.py::test_oauth_flow_docker -v
        echo ""
        if [ -n "$PRODUCTION_HOST" ]; then
            echo "4️⃣  Production environment..."
            pytest tests/test_oauth_integration.py::test_oauth_flow_production -v
        else
            echo "⏭️  Skipping production tests (PRODUCTION_HOST not set)"
        fi
        ;;
    
    *)
        echo "Usage: $0 [docker|production|health|config|all]"
        echo ""
        echo "Environments:"
        echo "  docker      - Test OAuth in Docker/local environment (default)"
        echo "  production  - Test OAuth in production (requires PRODUCTION_HOST)"
        echo "  health      - Quick health check without credentials"
        echo "  config      - Validate OAuth configuration (prevents error redirects)"
        echo "  all         - Run all tests"
        echo ""
        echo "Required environment variables:"
        echo "  TEST_LIBRECHAT_EMAIL      - LibreChat user email"
        echo "  TEST_LIBRECHAT_PASSWORD  - LibreChat user password"
        echo "  PRODUCTION_HOST          - Production host URL (for production tests)"
        echo "  LIBRECHATMCP_URL         - LibreChatMCP base URL (default: http://localhost:3002)"
        exit 1
        ;;
esac

echo ""
echo "✅ Tests completed!"

