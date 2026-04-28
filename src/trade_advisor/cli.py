"""Typer CLI: `ta fetch`, `ta backtest`, `ta dashboard`, `ta config`, `ta data`."""

from __future__ import annotations

import asyncio
import getpass
import json
import logging
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from logging import getLogger
from pathlib import Path
from typing import NoReturn

import pandas as pd
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel, setup_logging
from trade_advisor.core.config import format_config_error, load_config
from trade_advisor.core.container import bootstrap
from trade_advisor.core.errors import DataError
from trade_advisor.core.secrets import SECRET_KEY_NAMES, set_key
from trade_advisor.data.cache import DataValidationError, get_ohlcv, load_cached, validate_ohlcv
from trade_advisor.data.validation import (
    AnomalySeverity,
    detect_anomalies,
)
from trade_advisor.evaluation.metrics import compute_metrics
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
    container = bootstrap()
    strategy_cls = container.strategy_registry["sma_cross"]
    strat = strategy_cls(fast=fast, slow=slow, allow_short=allow_short)
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


# ── data subcommand group ──────────────────────────────────────────────────────


data_app = typer.Typer(help="Data operations: fetch, validate, status")
app.add_typer(data_app, name="data")


def _output_result(data: dict, *, fmt: str, cons: Console) -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        _render_fetch_rich(data, cons)


def _output_error(message: str, *, fmt: str, exit_code: int = 1) -> NoReturn:
    if fmt == "json":
        print(json.dumps({"error": message, "exit_code": exit_code}), file=sys.stderr)
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=exit_code)


def _render_fetch_rich(data: dict, cons: Console) -> None:
    cons.print(
        f"[green]OK[/green] {data['symbol']}: {data['bar_count']} bars "
        f"{data.get('start_date', '?')} → {data.get('end_date', '?')}"
    )
    vr = data.get("validation", {})
    level = vr.get("level", "PASS")
    if level == "PASS":
        cons.print("  Validation: [green]PASS[/green]")
    elif level == "WARN":
        cons.print(f"  Validation: [yellow]WARN[/yellow] ({vr.get('warning_count', 0)} warnings)")
    else:
        cons.print(f"  Validation: [red]FAIL[/red] ({vr.get('error_count', 0)} errors)")
    for a in vr.get("anomalies", []):
        sev = a.get("severity", "WARNING")
        tag = "[red]ERROR[/red]" if sev == "ERROR" else "[yellow]WARN[/yellow]"
        cons.print(f"    {tag}: {a['message']}")


class _RetryExhausted(Exception):
    def __init__(self, message: str, attempts: int, last_exc: Exception) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_exc = last_exc


_RETRYABLE = (ConnectionError, TimeoutError, RuntimeError, DataError, DataValidationError)


def _fetch_with_retry(
    symbol: str,
    start: str | None,
    end: str | None,
    interval: str,
    *,
    refresh: bool = False,
    max_retries: int = 2,
    fetcher=None,
) -> tuple[pd.DataFrame, int]:
    max_retries = max(0, max_retries)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            df = get_ohlcv(
                symbol,
                start=start,
                end=end,
                interval=interval,
                refresh=refresh,
                fetcher=fetcher,
            )
            return df, attempt
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(2**attempt)
        except Exception:
            raise
    assert last_exc is not None
    raise _RetryExhausted(
        f"{last_exc} (after {max_retries + 1} attempt(s))",
        attempts=max_retries + 1,
        last_exc=last_exc,
    )


@data_app.command("fetch")
def data_fetch(
    symbol: str = typer.Option(..., help="Ticker symbol (e.g. SPY)"),
    start: str | None = typer.Option(None, help="Start date YYYY-MM-DD"),
    end: str | None = typer.Option(None, help="End date YYYY-MM-DD (exclusive)"),
    interval: str = typer.Option("1d", help="Bar interval (1d, 1h, 5m, etc.)"),
    refresh: bool = typer.Option(False, help="Ignore cache, fetch fresh data"),
    format: str = typer.Option("rich", help="Output format: rich or json"),
) -> None:
    try:
        cli_warnings: list[str] = []

        if start and end:
            try:
                s_dt = datetime.fromisoformat(start)
                e_dt = datetime.fromisoformat(end)
            except ValueError as exc:
                _output_error(f"Invalid date format: {exc}", fmt=format)
            if s_dt >= e_dt:
                _output_error("start date must be before end date", fmt=format)

        if start:
            try:
                start_dt = datetime.fromisoformat(start)
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=UTC)
                if start_dt > datetime.now(UTC):
                    cli_warnings.append(
                        "start date is in the future; fetching most recent available data"
                    )
            except ValueError:
                _output_error(f"Invalid start date: {start}", fmt=format)

        existing_df = load_cached(symbol, interval) if not refresh else None
        bars_before = len(existing_df) if existing_df is not None else 0

        df, _retries_used = _fetch_with_retry(symbol, start, end, interval, refresh=refresh)

        if df is None or (hasattr(df, "empty") and df.empty):
            _output_error(f"No data returned for symbol {symbol}", fmt=format)

        result = detect_anomalies(df, symbol=symbol)

        n_bars = len(df)
        if "timestamp" in df.columns:
            ts_min = df["timestamp"].min()
            ts_max = df["timestamp"].max()
        else:
            ts_min = df.index.min()
            ts_max = df.index.max()
        min_date = str(ts_min.date()) if n_bars > 0 else ""
        max_date = str(ts_max.date()) if n_bars > 0 else ""

        new_bars = max(0, n_bars - bars_before)
        if new_bars > 0:
            cli_warnings.append(f"Cache updated: {new_bars} new bars appended")

        anomalies_data = []
        for a in result.anomalies:
            anomalies_data.append(
                {
                    "severity": a.severity.value,
                    "action": a.action.value,
                    "message": a.message,
                    "row_index": str(a.row_index) if a.row_index is not None else None,
                    "column": a.column,
                }
            )

        output = {
            "symbol": symbol,
            "bar_count": n_bars,
            "start_date": min_date,
            "end_date": max_date,
            "interval": interval,
            "validation": {
                "level": result.level.value,
                "warning_count": result.warning_count,
                "error_count": result.error_count,
                "anomalies": anomalies_data,
            },
            "warnings": cli_warnings,
        }

        if format == "json":
            print(json.dumps(output, indent=2, default=str))
        else:
            _render_fetch_rich(output, console)
            for w in cli_warnings:
                console.print(f"  [yellow]Warning:[/yellow] {w}")

    except typer.Exit:
        raise
    except _RetryExhausted as exc:
        _output_error(str(exc), fmt=format)
    except (DataError, DataValidationError, RuntimeError) as exc:
        _output_error(str(exc), fmt=format)
    except Exception as exc:
        if _is_verbose():
            raise
        _output_error(str(exc), fmt=format)


@data_app.command("status")
def data_status(
    format: str = typer.Option("rich", help="Output format: rich or json"),
    symbol: str | None = typer.Option(None, help="Filter to single symbol"),
) -> None:
    try:
        symbols = _query_cached_symbols()

        if symbol:
            symbols = [s for s in symbols if s["symbol"] == symbol.upper()]
            if not symbols:
                _output_error(f"No cached data found for symbol {symbol.upper()}", fmt=format)

        if not symbols:
            if format == "json":
                print("[]")
            else:
                console.print(
                    "No cached data found. Run [cyan]ta data fetch --symbol SPY[/cyan] "
                    "to get started."
                )
            return

        if format == "json":
            print(json.dumps(symbols, indent=2, default=str))
        else:
            table = Table(title="Cached Data", show_header=True)
            table.add_column("Symbol", style="cyan")
            table.add_column("Interval")
            table.add_column("Bars", justify="right")
            table.add_column("Start")
            table.add_column("End")
            table.add_column("Warnings", style="yellow", justify="right")
            table.add_column("Errors", style="red", justify="right")
            table.add_column("Last Updated")
            table.add_column("Stale", justify="center")

            for s in symbols:
                sym_name = s["symbol"]
                if s["errors"] > 0:
                    sym_name = f"[red]{sym_name}[/red]"
                stale_text = "[yellow]⚠[/yellow]" if s["is_stale"] else "[green]✓[/green]"
                table.add_row(
                    sym_name,
                    s["interval"],
                    str(s["bar_count"]),
                    str(s["min_ts"]),
                    str(s["max_ts"]),
                    str(s["warnings"]),
                    str(s["errors"]),
                    str(s.get("last_updated", "")),
                    stale_text,
                )
            console.print(table)

    except typer.Exit:
        raise
    except Exception as exc:
        if _is_verbose():
            raise
        _output_error(str(exc), fmt=format)


@data_app.command("validate")
def data_validate(
    symbol: str = typer.Option(..., help="Ticker symbol to validate"),
    interval: str = typer.Option("1d", help="Bar interval"),
    format: str = typer.Option("rich", help="Output format: rich or json"),
) -> None:
    try:
        df = load_cached(symbol, interval)
        if df is None:
            _output_error(f"No cached data found for symbol {symbol}", fmt=format)

        result = detect_anomalies(df, symbol=symbol)

        category_counts: Counter[str] = Counter()
        anomalies_data = []
        for a in result.anomalies:
            cat = _categorize_anomaly(a.message)
            category_counts[cat] += 1
            anomalies_data.append(
                {
                    "severity": a.severity.value,
                    "action": a.action.value,
                    "message": a.message,
                    "row_index": str(a.row_index) if a.row_index is not None else None,
                    "column": a.column,
                    "category": cat,
                }
            )

        output = {
            "symbol": symbol,
            "interval": interval,
            "bar_count": len(df),
            "level": result.level.value,
            "warning_count": result.warning_count,
            "error_count": result.error_count,
            "anomalies": anomalies_data,
            "category_breakdown": dict(category_counts),
        }

        if format == "json":
            print(json.dumps(output, indent=2, default=str))
        else:
            _render_validate_rich(output, console)

        has_errors = any(a.severity == AnomalySeverity.ERROR for a in result.anomalies)
        if has_errors:
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as exc:
        if _is_verbose():
            raise
        _output_error(str(exc), fmt=format)


def _render_validate_rich(data: dict, cons: Console) -> None:
    cons.print(
        f"\n[bold]Validation: {data['symbol']}[/bold] "
        f"({data['bar_count']} bars, {data['interval']})"
    )
    level = data["level"]
    if level == "PASS":
        cons.print("  Result: [green]PASS[/green]")
    elif level == "WARN":
        cons.print(f"  Result: [yellow]WARN[/yellow] ({data['warning_count']} warnings)")
    else:
        cons.print(
            f"  Result: [red]FAIL[/red] "
            f"({data['error_count']} errors, {data['warning_count']} warnings)"
        )

    anomalies = data.get("anomalies", [])
    if anomalies:
        table = Table(title=f"Anomalies: {data['symbol']}", show_header=True)
        table.add_column("Severity", width=10)
        table.add_column("Category")
        table.add_column("Row", justify="right")
        table.add_column("Column")
        table.add_column("Message")
        for a in anomalies:
            sev = "[red]ERROR[/red]" if a["severity"] == "ERROR" else "[yellow]WARN[/yellow]"
            table.add_row(
                sev,
                a.get("category", ""),
                a.get("row_index", ""),
                a.get("column", ""),
                a["message"],
            )
        cons.print(table)

    breakdown = data.get("category_breakdown", {})
    if breakdown:
        parts = [f"{k}: {v}" for k, v in sorted(breakdown.items())]
        cons.print(f"  Summary: {', '.join(parts)}")


def _categorize_anomaly(message: str) -> str:
    ml = message.lower()
    if "nan" in ml:
        return "NaN gaps"
    if "outlier" in ml or "z-score" in ml:
        return "Price outliers"
    if "zero volume" in ml:
        return "Zero volume"
    if "gap" in ml and "price" in ml:
        return "Price gaps"
    if "duplicate" in ml:
        return "Duplicates"
    if "skeleton" in ml:
        return "Skeleton bars"
    if "invalid" in ml:
        return "Invalid bars"
    if "negative" in ml:
        return "Negative values"
    if "infinit" in ml:
        return "Infinite prices"
    if "timestamp" in ml:
        return "Timestamp issues"
    return "Other"


def _query_cached_symbols() -> list[dict]:
    from trade_advisor.core.config import DatabaseConfig as _DBC
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = _DBC()

    async def _fetch():
        async with DatabaseManager(config) as db:
            repo = DataRepository(db)
            rows = await db.read(
                "SELECT DISTINCT symbol, interval FROM ohlcv_cache ORDER BY symbol, interval"
            )
            results = []
            for sym, iv in rows:
                try:
                    bar_rows = await db.read(
                        "SELECT COUNT(*), MIN(timestamp), MAX(timestamp), MAX(created_at) "
                        "FROM ohlcv_cache WHERE symbol = ? AND interval = ?",
                        (sym, iv),
                    )
                    bar_count, min_ts, max_ts, last_updated = bar_rows[0]
                    freshness = await repo.check_freshness(sym, iv)
                    cached = load_cached(sym, iv)
                    warnings = 0
                    errors = 0
                    if cached is not None and len(cached) > 0:
                        vr = detect_anomalies(cached, symbol=sym)
                        warnings = vr.warning_count
                        errors = vr.error_count
                    results.append(
                        {
                            "symbol": sym,
                            "interval": iv,
                            "bar_count": bar_count,
                            "min_ts": str(min_ts)[:10] if min_ts else "",
                            "max_ts": str(max_ts)[:10] if max_ts else "",
                            "warnings": warnings,
                            "errors": errors,
                            "last_updated": str(last_updated) if last_updated else None,
                            "is_stale": freshness.is_stale,
                        }
                    )
                except Exception:
                    getLogger("trade_advisor.cli").warning(
                        "Failed to query status for %s/%s", sym, iv, exc_info=True
                    )
            return results

    try:
        return asyncio.run(_fetch())
    except Exception:
        getLogger("trade_advisor.cli").warning("Failed to query cached symbols", exc_info=True)
        return []


def _is_verbose() -> bool:
    return logging.getLogger("trade_advisor.cli").level <= logging.DEBUG


if __name__ == "__main__":
    app()
