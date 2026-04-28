set dotenv-load

dev:
    uv venv --python 3.12 && source .venv/bin/activate && uv pip install -e ".[dev]" && pre-commit install

test *args:
    source .venv/bin/activate && pytest -ra --strict-markers {{ args }}

test-integration:
    source .venv/bin/activate && pytest -m integration

lint:
    source .venv/bin/activate && ruff check src/ tests/ && ruff format --check src/ tests/

typecheck:
    source .venv/bin/activate && mypy src/

check: lint typecheck test

fix:
    source .venv/bin/activate && ruff check --fix src/ tests/ && ruff format src/ tests/

dashboard:
    source .venv/bin/activate && ta dashboard

migrate:
    source .venv/bin/activate && uv run python -m trade_advisor.infra.migrate
