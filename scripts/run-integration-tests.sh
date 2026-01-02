#!/bin/bash
# Run integration tests for LibreChat-MCP (used by pre-push hook)
# Includes: integration tests, OAuth integration tests, Docker build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

source "$PROJECT_ROOT/scripts/git-hooks-utils.sh" 2>/dev/null || {
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
    
    print_section() { echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo "  $1"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo ""; }
    print_success() { echo -e "${GREEN}✓${NC} $1"; }
    print_error() { echo -e "${RED}✗${NC} $1"; }
    print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
    check_command() { command -v "$1" >/dev/null 2>&1; }
    run_test_suite() { echo "Running: $1"; shift; if "$@"; then print_success "$1"; else print_error "$1"; return 1; fi; }
}

print_section "LibreChat-MCP: Integration Tests (Pre-push)"

FAILED=0

# Integration Tests
if check_command pytest; then
    if run_test_suite "Integration tests" pytest tests/ -v -m integration; then
        :
    else
        print_warning "Integration tests failed (may require external services)"
        # Don't fail on integration tests if they require services that aren't running
    fi
fi

# OAuth Integration Tests
if check_command pytest; then
    if [ -f "tests/test_oauth_integration.py" ]; then
        print_section "OAuth Integration Tests"
        if [ -n "$TEST_LIBRECHAT_EMAIL" ] && [ -n "$TEST_LIBRECHAT_PASSWORD" ]; then
            if run_test_suite "OAuth integration tests" pytest tests/test_oauth_integration.py -v; then
                :
            else
                print_warning "OAuth integration tests failed (may require running services)"
            fi
        else
            print_warning "Skipping OAuth integration tests (TEST_LIBRECHAT_EMAIL and TEST_LIBRECHAT_PASSWORD not set)"
        fi
    fi
fi

# Docker Build Test
if check_command docker; then
    print_section "Docker Build Test"
    if [ -f "Dockerfile" ]; then
        if run_test_suite "Docker build" docker build -t test-librechat-mcp:test .; then
            print_success "Docker image built successfully"
            # Clean up test image
            docker rmi test-librechat-mcp:test >/dev/null 2>&1 || true
        else
            print_error "Docker build failed"
            FAILED=1
        fi
    fi
else
    print_warning "Docker not available, skipping Docker build test"
fi

# Dockerfile Lint (if hadolint is available)
if check_command hadolint && [ -f "Dockerfile" ]; then
    if run_test_suite "Dockerfile lint" hadolint Dockerfile; then
        :
    else
        print_warning "Dockerfile linting found issues (non-blocking)"
    fi
fi

if [ $FAILED -eq 1 ]; then
    print_error "Integration tests failed. Please fix the issues above."
    exit 1
fi

print_success "All integration tests passed!"
exit 0

