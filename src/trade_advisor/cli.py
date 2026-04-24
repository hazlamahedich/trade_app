"""Typer CLI: `ta fetch`, `ta backtest`, `ta dashboard`, `ta config`."""

from __future__ import annotations

import getpass
import logging
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel, setup_logging
from trade_advisor.core.config import format_config_error, load_config
from trade_advisor.core.secrets import SECRET_KEY_NAMES, set_key
from trade_advisor.data.cache import get_ohlcv, validate_ohlcv
from trade_advisor.evaluation.metrics import compute_metrics
from trade_advisor.strategies.sma_cross import SmaCross
from trade_advisor.tracking import mlflow_utils

app = typer.Typer(add_completion=False, help="Quant Trade Advisor CLI")
console = Console()
log = logging.getLogger("trade_advisor.cli")


@app.callback()
def _root(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    json_logs: bool = typer.Option(False, "--json-logs", help="Use JSON log output"),
) -> None:
    setup_logging(logging.DEBUG if verbose else logging.INFO, json_logs=json_logs)


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
        initial_cash=Decimal(str(initial_cash)),
        cost=CostModel(commission_pct=commission_pct, slippage_pct=slippage_pct),  # type: ignore[call-arg]
    )
    result = run_backtest(df, sig, cfg)
    metrics = compute_metrics(result.returns)

    _print_metrics(symbol, strat.describe().params, metrics, result.meta)

    with mlflow_utils.run(experiment=experiment, run_name=f"{symbol}_sma_{fast}_{slow}"):
        mlflow_utils.log_params(
            {
                "symbol": symbol,
                "interval": interval,
                "start": start,
                "end": end or "",
                "fast": fast,
                "slow": slow,
                "allow_short": allow_short,
                "commission_pct": commission_pct,
                "slippage_pct": slippage_pct,
            }
        )
        mlflow_utils.log_metrics(metrics.to_dict())


@app.command()
def dashboard() -> None:
    """Launch the Streamlit dashboard."""
    app_path = Path(__file__).parent / "ui" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    console.print(f"[cyan]Launching:[/cyan] {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


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


config_app = typer.Typer(help="Configuration management")
app.add_typer(config_app, name="config")


@config_app.command("validate")
def config_validate() -> None:
    """Validate configuration: fields present, types valid, keyring status."""
    errors: list[str] = []
    try:
        full = load_config()
        cfg = full.app
        console.print("[green]✓[/green] AppConfig loaded successfully")

        for section_name, section in [
            ("data", cfg.data),
            ("backtest", cfg.backtest),
            ("execution", cfg.execution),
            ("determinism", cfg.determinism),
            ("database", cfg.database),
            ("logging", cfg.logging),
        ]:
            console.print(f"  [cyan]{section_name}:[/cyan] {type(section).__name__}")

        if cfg.risk:
            console.print(f"  [cyan]risk:[/cyan] {type(cfg.risk).__name__}")
        else:
            console.print("  [dim]risk: (not configured)[/dim]")
        if full.secrets:
            console.print("  [cyan]secrets:[/cyan] SecretsConfig")
    except Exception as exc:
        if isinstance(exc, ValidationError):
            formatted = format_config_error(exc)
            errors.append(formatted)
            console.print(f"[red]✗[/red] {formatted}")
        else:
            errors.append(str(exc))
            console.print(f"[red]✗[/red] Config error: {exc}")

        suggestions = _suggest_from_env_example()
        if suggestions:
            console.print("\n[yellow]Suggested values from .env.example:[/yellow]")
            for line in suggestions:
                console.print(f"  [dim]{line}[/dim]")

    try:
        import keyring as kr

        kr.get_password("trade_advisor", "__probe__")
        console.print("[green]✓[/green] Keyring accessible")
    except Exception as exc:
        console.print(f"[yellow]⚠[/yellow] Keyring unavailable: {exc}")

    if errors:
        console.print(f"\n[red]Validation failed with {len(errors)} error(s)[/red]")
        raise typer.Exit(code=1)
    else:
        console.print("\n[green]Validation passed[/green]")


@config_app.command("set-key")
def config_set_key(
    key_name: str = typer.Argument(help="One of: " + ", ".join(SECRET_KEY_NAMES)),
) -> None:
    """Store an API key in the system keychain."""
    value = getpass.getpass(f"Enter value for {key_name}: ")
    if not value.strip():
        console.print("[red]✗[/red] Empty value not allowed")
        raise typer.Exit(code=1)
    try:
        set_key(key_name, value)
        console.print(f"[green]✓[/green] Stored {key_name} in keychain")
    except ValueError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗[/red] Keyring error: {exc}")
        raise typer.Exit(code=1) from exc


def _suggest_from_env_example() -> list[str]:
    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    if not env_example.exists():
        return []
    lines: list[str] = []
    for raw in env_example.read_text().splitlines():
        stripped = raw.strip()
        if (
            stripped.startswith("#")
            and not stripped.startswith("# ──")
            and not stripped.startswith("# Copy")
        ):
            key_val = stripped.lstrip("# ").strip()
            if "=" in key_val:
                lines.append(key_val)
    return lines


if __name__ == "__main__":
    app()
