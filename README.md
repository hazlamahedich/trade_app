# Quant Trade Advisor

Local-first, open-source quant research platform. Native Apple Silicon (M1 Max). Free tools only.

## Phase 1 scope

End-to-end loop for one symbol and one rule-based strategy:

- yfinance loader with Parquet cache
- Base `Strategy` interface with SMA crossover reference
- vectorbt backtest with transaction costs
- Core metrics (CAGR, Sharpe, max drawdown)
- MLflow experiment tracking (local file store)
- Typer CLI: `ta fetch`, `ta backtest`
- Streamlit dashboard

## Setup (M1 Max)

Recommended: [uv](https://github.com/astral-sh/uv) for fast, reproducible installs.

```bash
# One-time
curl -LsSf https://astral.sh/uv/install.sh | sh

# In repo root
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install
```

Or with stdlib `venv` + `pip`:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```bash
# Fetch 10 years of SPY daily data
ta fetch SPY --start 2015-01-01

# Backtest SMA(20, 50) crossover on SPY
ta backtest SPY --fast 20 --slow 50

# Launch the dashboard
ta dashboard
# (or: streamlit run src/trade_advisor/ui/app.py)

# Browse experiments
mlflow ui --backend-store-uri ./mlruns
```

## Layout

```
src/trade_advisor/
  data/        # yfinance source + parquet cache + validators
  features/    # (phase 2+) indicators, engineered features
  strategies/  # base class + SMA crossover
  backtest/    # vectorbt engine, cost model
  evaluation/  # metrics, (phase 2) walk-forward
  ml/          # (phase 3) pipelines, CV, models
  tracking/    # mlflow helpers
  ui/          # streamlit app
  cli.py       # typer CLI entry point
tests/
configs/       # yaml strategy configs
data_cache/    # local parquet cache (gitignored)
mlruns/        # mlflow artifacts (gitignored)
```

## Testing

```bash
pytest                       # unit tests only (offline)
pytest -m integration        # network-dependent tests
pytest --cov=trade_advisor   # coverage
```

## Disclaimer

Research and educational software. Not investment advice. No warranty.
