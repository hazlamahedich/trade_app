# AGENTS.md

## Commands

```bash
# Setup (from repo root)
uv venv --python 3.11 && source .venv/bin/activate && uv pip install -e ".[dev]"
pre-commit install

# Lint → format → typecheck (run in this order)
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/

# Test
pytest                                    # unit only (offline, no network)
pytest -m integration                     # network-dependent (yfinance calls)
pytest tests/test_strategy.py             # single file
pytest --cov=trade_advisor                # coverage
pytest -ra --strict-markers               # full strict run (matches CI)

# Run the app
ta fetch SPY --start 2015-01-01           # fetch + cache OHLCV
ta backtest SPY --fast 20 --slow 50       # SMA backtest + MLflow log
ta dashboard                              # Streamlit UI

# Sync toolchain memories
./scripts/sync-all.sh                     # BMAD + Serena + Graphify sync
./scripts/sync-all.sh --graphify-update   # also rebuild graph
```

## Architecture

- **Package**: `src/trade_advisor/` (installed as `trade_advisor`, CLI entry point `ta`)
- **Config**: `pydantic` models in `config.py`; YAML strategy configs in `configs/`
- **Data flow**: yfinance → `data/cache.py` (Parquet at `data_cache/ohlcv/<SYMBOL>/<INTERVAL>/`) → strategies → backtest engine → metrics → MLflow tracking
- **Strategy pattern**: Subclass `strategies/base.py::Strategy`, implement `generate_signals()` returning `{-1, 0, +1}` Series. Must shift by 1 bar to prevent lookahead bias.
- **Backtest engine**: `backtest/engine.py` — vectorized pandas/numpy (not vectorbt yet). Signal executed at same bar's close.
- **Experiment tracking**: `tracking/mlflow_utils.py`, local file store at `mlruns/`

## Key Conventions

- Python 3.11+, Apple Silicon (M1 Max), free/open-source deps only
- `ruff` for lint+format (line-length 100, E501 ignored, strict rule set)
- `mypy` with `ignore_missing_imports=true`, `strict=false`
- `pytest` markers: `@pytest.mark.integration` for network tests; default run is offline
- Tests use `conftest._synthetic_ohlcv()` for deterministic fixture data (seed=42)
- `__future__.annotations` in every module
- Signals convention: `+1` long, `0` flat, `-1` short

## Planning Artifacts

BMAD planning docs live in `_bmad-output/planning-artifacts/`:
- `Quant_Trade_Advisor_PRD.md` — PRD v1.1 (93 requirements)
- `architecture.md` — system design with component contracts
- `epics.md` — 7 epics with user stories
- `ux-design-specification.md` — UX flows and components
- `implementation-readiness-report-2026-04-24.md` — readiness assessment (90/100, READY)

Read these before starting implementation work. The project is post-readiness, pre-Sprint-0.

## Toolchain Integrations

- **Serena**: `.serena/` — project activated for symbol-level code navigation and memory
- **Graphify**: `graphify-out/` — knowledge graph; git hooks auto-rebuild on commit/checkout
- **BMAD**: `_bmad/` config, `_bmad-output/` generated docs
- **OpenCode**: `.opencode/opencode.json` — graphify plugin registered
- **Sync bridges**: `scripts/` contains `bmad-to-serena.py`, `graphify-to-serena.py`, `serena-context-for-bmad.py`, `sync-all.sh`

## Gotchas

- `data_cache/` and `mlruns/` are gitignored — they're created on first run
- `config.py` auto-creates `data_cache/` and `mlruns/` at import time via `mkdir`
- `pandas-ta` version `0.3.14b` has the `b` suffix — not a typo
- The `backtest/engine.py` docstring mentions vectorbt but the engine is pure pandas/numpy
- Phase 2+ directories (`features/`, `ml/`) exist but are empty stubs
