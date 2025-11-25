#!/usr/bin/env bash
# Lint and test script for ci-helper
# Runs all quality checks: ruff, basedpyright, and pytest

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Running code quality checks..."
echo ""

# Step 1: Ruff linting
echo "📝 Step 1/4: Running ruff check..."
if uv run ruff check . --fix; then
    echo -e "${GREEN}✓${NC} Ruff check passed"
else
    echo -e "${RED}✗${NC} Ruff check failed"
    exit 1
fi
echo ""

# Step 2: Ruff formatting
echo "🎨 Step 2/4: Running ruff format..."
if uv run ruff format .; then
    echo -e "${GREEN}✓${NC} Ruff format passed"
else
    echo -e "${RED}✗${NC} Ruff format failed"
    exit 1
fi
echo ""

# Step 3: Type checking
echo "🔎 Step 3/4: Running basedpyright type checking..."
if uv run basedpyright src/; then
    echo -e "${GREEN}✓${NC} Type checking passed"
else
    echo -e "${RED}✗${NC} Type checking failed"
    exit 1
fi
echo ""

# Step 4: Tests
echo "🧪 Step 4/4: Running pytest..."
if uv run pytest; then
    echo -e "${GREEN}✓${NC} All tests passed"
else
    echo -e "${RED}✗${NC} Tests failed"
    exit 1
fi
echo ""

echo -e "${GREEN}✨ All checks passed successfully!${NC}"
