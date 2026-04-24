"""Streamlit dashboard for Quant Trade Advisor — Phase 1 stub."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.data.cache import get_ohlcv, validate_ohlcv
from trade_advisor.evaluation.metrics import compute_metrics, drawdown_series
from trade_advisor.strategies.sma_cross import SmaCross

st.set_page_config(page_title="Quant Trade Advisor", layout="wide")

st.title("Quant Trade Advisor")
st.caption("Phase 1 — SMA crossover backtest. Research tool, not investment advice.")

# ---------- Sidebar controls ----------
with st.sidebar:
    st.header("Run configuration")
    symbol = st.text_input(
        "Symbol", value="SPY", help="yfinance ticker. e.g. SPY, AAPL, EURUSD=X, BTC-USD"
    )
    start = st.text_input("Start date", value="2015-01-01")
    end = st.text_input("End date (blank = today)", value="")
    interval = st.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)

    st.divider()
    st.subheader("Strategy")
    fast = st.number_input("Fast SMA", min_value=2, max_value=200, value=20, step=1)
    slow = st.number_input("Slow SMA", min_value=3, max_value=400, value=50, step=1)
    allow_short = st.checkbox("Allow short", value=False)

    st.divider()
    st.subheader("Costs")
    commission_pct = st.number_input(
        "Commission %", min_value=0.0, max_value=0.01, value=0.0, step=0.0001, format="%.4f"
    )
    slippage_pct = st.number_input(
        "Slippage %", min_value=0.0, max_value=0.01, value=0.0005, step=0.0001, format="%.4f"
    )
    initial_cash = st.number_input(
        "Initial cash ($)", min_value=1_000.0, value=100_000.0, step=1_000.0
    )

    run_btn = st.button("Run backtest", type="primary", use_container_width=True)


@st.cache_data(show_spinner="Fetching data...")
def _load(symbol: str, start: str, end: str | None, interval: str) -> pd.DataFrame:
    df = get_ohlcv(symbol, start=start or None, end=end or None, interval=interval)
    return df


def _chart(
    ohlcv: pd.DataFrame,
    equity: pd.Series,
    dd: pd.Series,
    fast_series: pd.Series,
    slow_series: pd.Series,
) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.5, 0.3, 0.2],
        vertical_spacing=0.04,
        subplot_titles=("Price & SMAs", "Strategy Equity", "Drawdown"),
    )
    ts = pd.to_datetime(ohlcv["timestamp"])
    price = ohlcv["adj_close"] if "adj_close" in ohlcv.columns else ohlcv["close"]

    fig.add_trace(go.Scatter(x=ts, y=price, name="Price", line={"color": "#444"}), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=ts, y=fast_series.values, name=f"SMA {fast}", line={"color": "#2E75B6"}),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=ts, y=slow_series.values, name=f"SMA {slow}", line={"color": "#E67E22"}),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(x=equity.index, y=equity.values, name="Equity", line={"color": "#2ECC71"}),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=dd.index, y=dd.values, name="Drawdown", fill="tozeroy", line={"color": "#E74C3C"}
        ),
        row=3,
        col=1,
    )

    fig.update_layout(height=760, showlegend=True, margin={"l": 40, "r": 20, "t": 50, "b": 40})
    fig.update_yaxes(tickformat=".0%", row=3, col=1)
    return fig


if run_btn:
    if fast >= slow:
        st.error("Fast SMA must be strictly less than Slow SMA.")
        st.stop()

    try:
        ohlcv = _load(symbol, start, end or None, interval)
    except Exception as exc:
        st.error(f"Data fetch failed: {exc}")
        st.stop()

    warnings = validate_ohlcv(ohlcv, symbol)
    for w in warnings:
        st.warning(w)

    strat = SmaCross(fast=int(fast), slow=int(slow), allow_short=allow_short)
    sig = strat.generate_signals(ohlcv)

    cfg = BacktestConfig(
        initial_cash=float(initial_cash),
        cost=CostModel(
            commission_pct=float(commission_pct),  # type: ignore[call-arg]
            slippage_pct=float(slippage_pct),
        ),
    )
    result = run_backtest(ohlcv, sig, cfg)
    metrics = compute_metrics(result.returns)

    # Benchmark: buy & hold
    price_series = (ohlcv["adj_close"] if "adj_close" in ohlcv.columns else ohlcv["close"]).copy()
    price_series.index = pd.to_datetime(ohlcv["timestamp"])
    bh_ret = price_series.pct_change().fillna(0.0)
    bh_metrics = compute_metrics(bh_ret)

    # ---- Metrics row ----
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("CAGR", f"{metrics.cagr:.2%}", f"{metrics.cagr - bh_metrics.cagr:+.2%} vs B&H")
    col2.metric("Sharpe", f"{metrics.sharpe:.2f}", f"{metrics.sharpe - bh_metrics.sharpe:+.2f}")
    col3.metric("Max DD", f"{metrics.max_drawdown:.2%}")
    col4.metric("Calmar", f"{metrics.calmar:.2f}")
    col5.metric("Trades", f"{result.meta['n_trades']:,}")

    # ---- Chart ----
    close = price_series
    fast_ma = close.rolling(int(fast), min_periods=int(fast)).mean()
    slow_ma = close.rolling(int(slow), min_periods=int(slow)).mean()
    equity = result.equity
    dd = drawdown_series(equity)
    st.plotly_chart(_chart(ohlcv, equity, dd, fast_ma, slow_ma), use_container_width=True)

    # ---- Tables ----
    tab1, tab2, tab3 = st.tabs(["Strategy metrics", "Buy & Hold", "Trades"])
    with tab1:
        st.dataframe(pd.DataFrame([metrics.to_dict()]).T.rename(columns={0: "value"}))
    with tab2:
        st.dataframe(pd.DataFrame([bh_metrics.to_dict()]).T.rename(columns={0: "value"}))
    with tab3:
        if result.trades.empty:
            st.info("No trades generated.")
        else:
            st.dataframe(result.trades, use_container_width=True)

else:
    st.info("Configure a run in the sidebar and click **Run backtest**.")
    st.markdown(
        "**Tips for first run:** try `SPY` with fast=20, slow=50, start=2015-01-01. "
        "Compare the strategy metrics against Buy & Hold — an honest benchmark is "
        "the first defense against overfitting."
    )
