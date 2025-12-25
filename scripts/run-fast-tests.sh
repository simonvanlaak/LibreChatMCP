#!/bin/bash
# Run fast tests for LibreChatMCP (used by pre-commit hook)
# Includes: lint, format, unit tests, OAuth config validation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

source "$PROJECT_ROOT/scripts/git-hooks-utils.sh" 2>/dev/null || {
    # Fallback if not available
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

print_section "LibreChatMCP: Fast Tests (Pre-commit)"

FAILED=0

# Linting
if check_command ruff; then
    if run_test_suite "Ruff linting" ruff check .; then
        :
    else
        print_error "Ruff found issues. Run 'ruff check --fix .' to auto-fix some issues."
        FAILED=1
    fi
elif check_command flake8; then
    if run_test_suite "Flake8 linting" flake8 .; then
        :
    else
        FAILED=1
    fi
else
    print_warning "No linter found (ruff or flake8)"
fi

# Formatting
if check_command ruff; then
    if run_test_suite "Ruff formatting check" ruff format --check .; then
        :
    else
        print_error "Code formatting issues. Run 'ruff format .' to fix."
        FAILED=1
    fi
elif check_command black; then
    if run_test_suite "Black formatting check" black --check .; then
        :
    else
        print_error "Code formatting issues. Run 'black .' to fix."
        FAILED=1
    fi
else
    print_warning "No formatter found (ruff or black)"
fi

# Type Checking (optional)
if check_command mypy; then
    if [ -f "pyproject.toml" ] || [ -f "setup.cfg" ]; then
        if run_test_suite "MyPy type checking" mypy . 2>/dev/null || true; then
            :
        else
            print_warning "MyPy found type issues (non-blocking)"
        fi
    fi
fi

# Unit Tests (excluding integration)
if check_command pytest; then
    if run_test_suite "Unit tests" pytest tests/ -v -m "not integration" --tb=short; then
        :
    else
        FAILED=1
    fi
else
    print_error "pytest not found"
    FAILED=1
fi

# Fast OAuth Config Test
if check_command pytest; then
    if [ -f "tests/test_oauth_integration.py" ]; then
        if run_test_suite "OAuth config validation" pytest tests/test_oauth_integration.py::test_oauth_configuration_prevents_error_redirect -v; then
            :
        else
            print_error "OAuth configuration validation failed"
            FAILED=1
        fi
    fi
fi

if [ $FAILED -eq 1 ]; then
    print_error "Fast tests failed. Please fix the issues above."
    exit 1
fi

print_success "All fast tests passed!"
exit 0

