#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: scripts/test-changed.sh <base-ref> [extra-pytest-args...]"
    echo "Example: scripts/test-changed.sh main"
    echo "Example: scripts/test-changed.sh HEAD~3 --verbose"
    exit 1
fi

BASE_REF="${1}"
shift

CHANGED=$(git diff --name-only --diff-filter=ACMR "$BASE_REF" -- '*.py' 2>/dev/null || echo "")

if [ -z "$CHANGED" ]; then
    echo "No Python files changed since $BASE_REF"
    exit 0
fi

TEST_FILES=""
for f in $CHANGED; do
    test_path="tests/test_$(basename "${f%.py}").py"
    if [ -f "$test_path" ]; then
        TEST_FILES="$TEST_FILES $test_path"
    fi
done

if [ -z "$TEST_FILES" ]; then
    echo "No matching test files found for changed sources"
    echo "Changed files:"
    echo "$CHANGED"
    exit 0
fi

source .venv/bin/activate
echo "Running tests for changed files:$TEST_FILES"
exec pytest $TEST_FILES "$@"
