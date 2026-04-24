"""Typer CLI: `ta fetch`, `ta backtest`, `ta dashboard`."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel, setup_logging
from trade_advisor.data.cache import get_ohlcv, validate_ohlcv
from trade_advisor.evaluation.metrics import compute_metrics
from trade_advisor.strategies.sma_cross import SmaCross
from trade_advisor.tracking import mlflow_utils

app = typer.Typer(add_completion=False, help="Quant Trade Advisor CLI")
console = Console()
log = logging.getLogger("trade_advisor.cli")


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    setup_logging(logging.DEBUG if verbose else logging.INFO)


@app.command()
def fetch(
    symbol: str,
    start: str = typer.Option("2015-01-01", help="YYYY-MM-DD"),
    end: str | None = typer.Option(None, help="YYYY-MM-DD (exclusive)"),
    interval: str = typer.Option("1d"),
    refresh: bool = typer.Option(False, help="Ignore cache"),
) -> None:
    """Fetch OHLCV data and cache to Parquet."""
    df = get_ohlcv(symbol, start=start, end=end, interval=interval, refresh=refresh)
    warnings = validate_ohlcv(df, symbol)
    for w in warnings:
        console.print(f"[yellow]warn:[/yellow] {w}")
    console.print(
        f"[green]OK[/green] {symbol}: {len(df)} bars "
        f"{df['timestamp'].min().date()} → {df['timestamp'].max().date()}"
    )


@app.command()
def backtest(
    symbol: str,
    fast: int = typer.Option(20, help="Fast SMA window"),
    slow: int = typer.Option(50, help="Slow SMA window"),
    start: str = typer.Option("2015-01-01"),
    end: str | None = typer.Option(None),
    interval: str = typer.Option("1d"),
    allow_short: bool = typer.Option(False),
    commission_pct: float = typer.Option(0.0),
    slippage_pct: float = typer.Option(0.0005),
    initial_cash: float = typer.Option(100_000.0),
    experiment: str = typer.Option("sma_cross"),
) -> None:
    """Backtest an SMA crossover on a symbol and log to MLflow."""
    df = get_ohlcv(symbol, start=start, end=end, interval=interval)
    strat = SmaCross(fast=fast, slow=slow, allow_short=allow_short)
    sig = strat.generate_signals(df)

    cfg = BacktestConfig(
        initial_cash=initial_cash,
        cost=CostModel(commission_pct=commission_pct, slippage_pct=slippage_pct),
    )
    result = run_backtest(df, sig, cfg)
    metrics = compute_metrics(result.returns)

    _print_metrics(symbol, strat.describe().params, metrics, result.meta)

    with mlflow_utils.run(experiment=experiment, run_name=f"{symbol}_sma_{fast}_{slow}"):
        mlflow_utils.log_params({
            "symbol": symbol,
            "interval": interval,
            "start": start,
            "end": end or "",
            "fast": fast,
            "slow": slow,
            "allow_short": allow_short,
            "commission_pct": commission_pct,
            "slippage_pct": slippage_pct,
        })
        mlflow_utils.log_metrics(metrics.to_dict())


@app.command()
def dashboard() -> None:
    """Launch the Streamlit dashboard."""
    app_path = Path(__file__).parent / "ui" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    console.print(f"[cyan]Launching:[/cyan] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)  # noqa: S603


def _print_metrics(symbol: str, params: dict, metrics, meta: dict) -> None:
    table = Table(title=f"Backtest: {symbol}  {params}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="magenta")

    rows = [
        ("Bars", f"{meta.get('bars', 0):,}"),
        ("Trades", f"{meta.get('n_trades', 0):,}"),
        ("Total Return", f"{metrics.total_return:.2%}"),
        ("CAGR", f"{metrics.cagr:.2%}"),
        ("Annual Vol", f"{metrics.annual_vol:.2%}"),
        ("Sharpe", f"{metrics.sharpe:.2f}"),
        ("Sortino", f"{metrics.sortino:.2f}"),
        ("Max DD", f"{metrics.max_drawdown:.2%}"),
        ("Calmar", f"{metrics.calmar:.2f}"),
        ("Win Rate", f"{metrics.win_rate:.2%}"),
    ]
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)


if __name__ == "__main__":
    app()
