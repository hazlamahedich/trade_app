**Product Requirements Document**

**Quant Trade Advisor**

*ML-powered backtesting, walk-forward optimization, and advisory
platform*

Version 0.1 (Draft)

Target Platform: Apple M1 Max (macOS, arm64)

Stack: Python 3.11+, Free & Open Source only

1\. Executive Summary

Quant Trade Advisor is a local-first, open-source research and trading
advisory platform designed to run natively on Apple Silicon (M1 Max). It
ingests historical market data via yfinance (with pluggable alternative
sources), backtests rule-based and ML-driven strategies with realistic
transaction costs, validates them using walk-forward optimization and
purged cross-validation, and surfaces actionable advisories through an
interactive dashboard.

The platform targets four asset classes in priority order: stocks/ETFs,
forex, crypto, and options. The initial release focuses on stocks and
forex. ML workflows emphasize leak-free feature engineering, honest
out-of-sample evaluation, and baseline comparison --- avoiding the
common failure modes that make most retail ML trading projects
unreliable.

This document describes the full product vision, technical architecture,
and a four-phase delivery plan. Phase 1 (foundation) is scaffolded
alongside this PRD as a working starter project.

2\. Goals and Non-Goals

2.1 Goals

- Serve as a personal trading research tool the user actually trusts and
  runs locally.

- Teach the user quantitative finance and machine learning through
  hands-on, reproducible workflows.

- Function as a portfolio-grade showcase project demonstrating software,
  data, and ML engineering.

- Provide an architecture clean enough to eventually productize
  (multi-user, cloud-ready).

- Support stocks/ETFs and forex at launch; crypto and options in later
  phases.

- Run entirely on free, open-source tooling --- no paid data, no paid
  cloud dependencies required.

- Leverage Apple Silicon natively (arm64 wheels, Metal/MPS acceleration
  where relevant).

2.2 Non-Goals (initial release)

- Automated live order execution. The system produces advisories, not
  automated trades.

- Tick-level or level-2 order book analysis --- yfinance and free
  sources do not support this reliably.

- Historical options chain backtesting. yfinance exposes only current
  chains; historical options data is deferred to Phase 3+ with optional
  paid upgrade path.

- A claim of a profitable \'edge.\' The product\'s value is rigorous
  research infrastructure, not a guaranteed alpha source.

- Multi-user authentication, billing, or SaaS infrastructure in Phase
  1-3.

3\. Target Users and Personas

3.1 Primary: The Learning Quant (you)

Some Python experience, learning ML and quant simultaneously. Wants an
end-to-end project that teaches through doing and produces credible,
reusable infrastructure. Values clarity, reproducibility, and honest
evaluation over flashy performance claims.

3.2 Secondary: Retail Systematic Trader

Wants to research strategies before deploying to a broker. Needs solid
backtest hygiene, walk-forward validation, and clear risk metrics.
Typically has intermediate Python skills.

3.3 Tertiary: ML/Finance Portfolio Reviewer

A hiring manager or peer reviewer who wants to see evidence of good
engineering practice: modular design, tests, honest evaluation, tracked
experiments. They spend 10 minutes in the repo before forming an
opinion.

4\. Functional Requirements

4.1 Data Layer

- Fetch OHLCV data from yfinance for stocks, ETFs, forex pairs (e.g.,
  EURUSD=X), indices, and crypto (e.g., BTC-USD).

- Cache raw and adjusted data to local Parquet files partitioned by
  symbol and interval.

- Handle stock splits, dividends, and corporate actions correctly (use
  yfinance\'s auto_adjust for returns analysis, keep raw OHLCV
  separately for charting).

- Provide pluggable data source interface. yfinance is default; Stooq,
  Alpha Vantage free tier, and FRED planned as alternates.

- Refresh stale cache entries incrementally rather than re-downloading
  full history.

- Validate downloaded data: check for NaN runs, duplicate timestamps,
  impossible prices, zero-volume days on liquid instruments.

4.2 Strategy Engine

- Support rule-based strategies (e.g., SMA cross, Bollinger mean
  reversion, momentum) defined as pluggable Python classes.

- Support ML strategies that output a signal (long/short/flat, or
  position size in \[-1, 1\]).

- Each strategy defines: universe, features, signal generation, position
  sizing, entry/exit rules.

- Strategies must be serializable so a run can be fully reproduced from
  stored config.

4.3 Backtesting

- Vectorized backtests via vectorbt for speed; event-driven alternative
  via backtesting.py for complex logic.

- Transaction cost model: fixed commission, percentage fee, fixed
  spread, volatility-scaled slippage.

- Portfolio-level metrics: total return, CAGR, Sharpe, Sortino, Calmar,
  max drawdown, win rate, profit factor, turnover.

- Trade-level analysis: holding period distribution, MFE/MAE, entry/exit
  price distributions.

- Benchmark comparison against buy-and-hold of the same universe.

4.4 Walk-Forward Optimization

- Rolling and anchored walk-forward schemes with configurable train/test
  window sizes.

- In-sample hyperparameter search via Optuna with TPE sampler and median
  pruning.

- Out-of-sample evaluation using parameters frozen from the prior
  in-sample window.

- Walk-forward equity curve stitched from OOS segments only --- never
  includes IS results.

- Report walk-forward efficiency ratio (OOS performance / IS
  performance) to detect overfitting.

4.5 Machine Learning Pipeline

- Feature library: returns over N lookbacks, rolling volatility,
  technical indicators (pandas-ta), regime features (HMM states,
  volatility regime), calendar features.

- Leak prevention: features are built using only information available
  at time t; targets use strictly future returns; embargoed splits
  prevent information bleed.

- Models: logistic regression and linear baseline; XGBoost and LightGBM
  as main classical models; PyTorch (MPS) for LSTM/Transformer
  experiments in Phase 4.

- Purged k-fold cross-validation following López de Prado, with
  configurable embargo length.

- Probability calibration (Platt scaling or isotonic) for classifiers
  whose outputs drive position sizing.

- Mandatory naive baselines: random signal, always-long,
  previous-day-return; any ML model must beat these by a meaningful
  margin on OOS Sharpe to be considered.

4.6 Experiment Tracking

- MLflow tracking server running locally, logging parameters, metrics,
  artifacts (equity curves, confusion matrices, feature importances).

- Every backtest and every ML training run creates a tracked experiment
  with a deterministic run ID.

- Configs stored as YAML and logged as MLflow artifacts for full
  reproducibility.

4.7 Advisory Output

- For each configured symbol and strategy: current signal
  (long/short/flat), confidence, position size, suggested stop and
  target.

- Risk summary: portfolio-level exposure, concentration, correlation to
  benchmark.

- Clear provenance: which strategy, which parameters (and when they were
  last validated), which OOS performance supports this advisory.

- Explicit uncertainty disclosure --- the app displays when a
  strategy\'s OOS performance has degraded or its walk-forward
  confidence has dropped below threshold.

4.8 User Interface

- Streamlit dashboard as the primary UI in Phase 1-2.

- Pages: Data Explorer, Strategy Lab, Backtest Viewer, Walk-Forward
  Results, ML Lab, Advisories.

- Optional FastAPI + React frontend in Phase 4 if productization is
  pursued.

5\. Non-Functional Requirements

5.1 Performance

- Full backtest of 10 years daily data across 50 symbols: under 10
  seconds on M1 Max using vectorbt.

- Walk-forward optimization with 100 trial Optuna search, 10 folds, 50
  symbols: under 15 minutes on M1 Max.

- XGBoost training on 10 years of daily multi-feature data: under 60
  seconds per fold.

5.2 Reproducibility

- All randomness seeded. Config + data snapshot + code git-hash uniquely
  determine any result.

- Dependencies pinned via uv or poetry; lock file committed.

5.3 Platform

- Native arm64 wheels wherever available. No x86-only dependencies.

- PyTorch must use Metal Performance Shaders (MPS) when GPU acceleration
  is requested.

5.4 Code Quality

- Type hints throughout; mypy in CI.

- Unit tests for every non-trivial function; pytest with coverage
  reporting.

- Integration tests for data loaders (offline fixtures) and backtest
  end-to-end.

- Ruff for linting, Black for formatting, pre-commit hooks enforced.

6\. Technology Stack

  ---------------- ------------------------ ------------------------------
  **Layer**        **Technology**           **Rationale**

  Language         Python 3.11+             Mature ecosystem, arm64
                                            support, strong typing

  Package mgmt     uv                       Fast, reproducible,
                                            arm64-native

  Data source      yfinance,                Free, broad coverage
                   pandas-datareader        

  Storage          Parquet + DuckDB         Columnar, fast, local,
                                            zero-config

  Indicators       pandas-ta                130+ indicators, pandas-native

  Backtesting      vectorbt                 Vectorized, GPU-friendly, M1
  (fast)                                    fast

  Backtesting      backtesting.py           Event-driven, simple API
  (flexible)                                

  Optimization     Optuna                   TPE, pruning, SQLite storage

  Classical ML     scikit-learn, XGBoost,   Native arm64 wheels
                   LightGBM                 

  Deep learning    PyTorch (MPS backend)    M1 GPU acceleration

  Regime models    hmmlearn, ruptures       HMM and change-point detection

  NLP/Sentiment    FinBERT, Hugging Face    Open-source financial NLP
                   transformers             

  Tracking         MLflow                   Free, local server, arm64
                                            compatible

  Dashboard        Streamlit                Fast Python-native UI

  Future API       FastAPI + React          Productization path

  Testing          pytest, hypothesis       Property-based and unit
                                            testing

  CI/lint/format   Ruff, Black, mypy,       Standard modern tooling
                   pre-commit               
  ---------------- ------------------------ ------------------------------

7\. System Architecture

The system follows a layered architecture. Each layer depends only on
layers beneath it. Cross-cutting concerns (logging, config, caching) are
centralized.

7.1 Layers

- Source adapters, cache, validators. Produces clean OHLCV DataFrames.

- Indicators, engineered features, targets. Strict no-lookahead
  contract.

- Signal producers (rule-based or ML-based) implementing a common
  interface.

- Simulates portfolio evolution given signals and cost model.

- Metrics, walk-forward scheduling, baseline comparison.

- MLflow experiment logging and artifact storage.

- Streamlit dashboard, CLI, and future REST API.

7.2 Directory Structure

The Phase 1 scaffold ships with the following layout:

trade_advisor/ src/trade_advisor/ data/ \# sources, cache, validators
features/ \# indicators, engineered features strategies/ \# base class +
concrete strategies backtest/ \# vectorbt wrappers, cost models
evaluation/ \# metrics, walk-forward ml/ \# pipelines, CV, models
tracking/ \# MLflow helpers ui/ \# streamlit app cli.py \# typer CLI
tests/ configs/ \# yaml strategy configs data_cache/ \# local parquet
cache (gitignored) mlruns/ \# mlflow artifacts (gitignored)
pyproject.toml README.md

8\. Data Model

8.1 OHLCV Table (canonical)

  --------------- ------------------ -------------------------------------
  **Column**      **Type**           **Notes**

  symbol          string             Ticker in source format (AAPL,
                                     EURUSD=X, BTC-USD)

  interval        string             1d, 1h, etc.

  timestamp       datetime64\[ns,    Bar close time, timezone-aware
                  UTC\]              

  open            float64            Unadjusted

  high            float64            Unadjusted

  low             float64            Unadjusted

  close           float64            Unadjusted

  adj_close       float64            Split+dividend adjusted

  volume          int64              

  source          string             Data source tag (yfinance, stooq,
                                     etc.)
  --------------- ------------------ -------------------------------------

8.2 Storage

- Parquet files under
  data_cache/ohlcv/symbol=\<SYMBOL\>/interval=\<INTERVAL\>/part.parquet

- DuckDB views over Parquet for ad-hoc analytical queries in notebooks.

- MLflow artifacts under mlruns/ (local file store).

9\. Phased Delivery Roadmap

9.1 Phase 1 --- Foundation (Weeks 1-3)

Goal: a working, testable end-to-end loop for one symbol and one simple
strategy.

- Project scaffold, packaging, linting, testing, CI.

- yfinance data loader with Parquet cache and validators.

- Base Strategy interface and SMA-crossover reference implementation.

- Minimal vectorbt backtest wrapper with transaction costs.

- Core metrics module (returns, Sharpe, drawdown).

- Typer CLI: fetch, backtest, report.

- Streamlit dashboard stub with one page: run SMA backtest on SPY and
  view equity curve.

- MLflow local tracking for backtest runs.

- Test suite: unit tests for loader, strategy, metrics; one integration
  test of the full loop.

9.2 Phase 2 --- Robust Backtesting (Weeks 4-6)

- Additional strategies: Bollinger mean reversion, dual-momentum,
  breakout.

- Forex support: EURUSD=X, GBPUSD=X, USDJPY=X, with pip-aware position
  sizing.

- Advanced cost model: volatility-scaled slippage, per-asset spread
  tables.

- Walk-forward engine with anchored and rolling modes.

- Optuna integration with SQLite storage and MLflow logging.

- Baseline comparison harness (buy-and-hold, random, previous-return).

- Dashboard pages: Walk-Forward Viewer, Strategy Comparison.

9.3 Phase 3 --- Machine Learning (Weeks 7-10)

- Feature engineering module with 40+ features and strict leak
  prevention.

- Purged k-fold CV implementation (López de Prado).

- ML strategy wrapper: model produces signals consumed by backtest
  layer.

- XGBoost and LightGBM classifiers with calibrated probabilities for
  position sizing.

- Feature importance (SHAP) logged to MLflow.

- Mandatory naive-baseline comparison in the dashboard --- no ML result
  displayed without it.

- Crypto asset class added (BTC-USD, ETH-USD).

9.4 Phase 4 --- Cutting Edge (Weeks 11+)

- Regime detection (HMM) gating strategy activation.

- Ensemble/stacked strategies with dynamic capital allocation (risk
  parity, Kelly-lite).

- News sentiment via FinBERT on free RSS/news feeds.

- PyTorch LSTM/Transformer experiments on MPS backend.

- Options Phase: read-only chain analytics (Black-Scholes IV, greeks) on
  live yfinance chains; historical options deferred or requires paid
  data source.

- Optional: FastAPI + React frontend, Dockerized deploy.

- Optional: reinforcement learning for position sizing
  (stable-baselines3 on MPS).

10\. Risks and Mitigations

  ------------------------ ---------------- ----------------------------------
  **Risk**                 **Likelihood**   **Mitigation**

  yfinance rate limits /   High             Aggressive caching, rate-limited
  data gaps                                 requests, pluggable alternate
                                            sources

  Lookahead bias in ML     High             Strict feature-building contract,
  features                                  purged CV, automated leak tests

  Overfitting in           High             Report WF efficiency ratio,
  walk-forward                              require OOS Sharpe \> naive
  optimization                              baseline

  Transaction costs kill   High             Include realistic costs from day
  ML edge                                   1, compare net-of-cost Sharpe

  No historical options    Certain          Defer options backtesting; support
  data on free sources                      chain analytics only

  User mistakes model      Medium           UI must show confidence intervals
  probability for                           and recent OOS degradation
  certainty                                 

  Scope creep (too many    High             Strict phase gates, each phase
  features too fast)                        must ship end-to-end before next
  ------------------------ ---------------- ----------------------------------

11\. Success Metrics

11.1 Engineering

- Test coverage \>= 80% on core modules (data, strategy, backtest,
  metrics).

- Full backtest pipeline runs from CLI and dashboard on a clean machine
  in under 10 minutes including data fetch.

- Every result reproducible from config + git hash.

11.2 Research

- At least one strategy demonstrates statistically meaningful OOS edge
  versus buy-and-hold on a diversified equity universe after costs.

- At least one ML model beats the strongest naive baseline by \>= 0.3
  OOS Sharpe on a 5-year walk-forward.

- No ML result shipped to dashboard without a paired baseline and
  walk-forward efficiency report.

11.3 Learning

- User can explain every component in the codebase without reference
  notes.

- User has read and implemented one technique from López de Prado,
  Advances in Financial Machine Learning.

12\. Open Questions

- Will the user eventually want paper-trading integration with a broker
  (e.g., Alpaca) in Phase 4?

- Should the advisory layer send notifications (email, push), or remain
  pull-only via dashboard?

- What is the preferred approach for news data: free RSS/Yahoo, or a
  paid source later?

- Is there an appetite for a multi-account portfolio overlay, or
  single-account focus?

13\. Disclaimer

This software is for research and educational purposes only. It is not
investment advice. Historical performance does not guarantee future
results. Any trading decisions made on the basis of signals produced by
this system are the sole responsibility of the user. No warranty of any
kind is provided.
