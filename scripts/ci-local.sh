#!/usr/bin/env bash
set -euo pipefail

VENV=".venv"
if [ ! -d "$VENV" ]; then
    echo "Creating venv..."
    uv venv --python 3.12
fi

source "$VENV/bin/activate"

echo "Installing dependencies..."
uv pip install -e ".[dev]"

echo "=== Running lint ==="
ruff check src/ tests/
ruff format --check src/ tests/

echo "=== Running mypy ==="
mypy src/

echo "=== Running unit tests ==="
pytest -x -m "not integration and not e2e"

echo "=== All CI checks passed ==="
