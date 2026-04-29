"""Unit tests for backtest/execution.py — OrderSpec, FillResult, MarketExecutionRouter."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from trade_advisor.backtest.execution import (
    FillResult,
    MarketExecutionRouter,
    OrderSpec,
)


class TestOrderSpec:
    def test_market_order_construction(self):
        spec = OrderSpec(side="buy", order_type="market", quantity=100)
        assert spec.side == "buy"
        assert spec.order_type == "market"
        assert spec.quantity == 100
        assert spec.limit_price is None
        assert spec.stop_price is None

    def test_frozen_immutability(self):
        spec = OrderSpec(side="buy", order_type="market", quantity=100)
        with pytest.raises(AttributeError):
            spec.quantity = 200  # type: ignore[misc]

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            OrderSpec(side="buy", order_type="market", quantity=-10)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="must be positive"):
            OrderSpec(side="sell", order_type="market", quantity=0)

    def test_limit_order_without_price_raises(self):
        with pytest.raises(ValueError, match="limit_price"):
            OrderSpec(side="buy", order_type="limit", quantity=10)

    def test_limit_order_zero_price_raises(self):
        with pytest.raises(ValueError, match="limit_price must be positive"):
            OrderSpec(side="buy", order_type="limit", quantity=10, limit_price=0.0)

    def test_limit_order_valid(self):
        spec = OrderSpec(side="buy", order_type="limit", quantity=10, limit_price=50.0)
        assert spec.limit_price == 50.0

    def test_stop_order_without_price_raises(self):
        with pytest.raises(ValueError, match="stop_price"):
            OrderSpec(side="sell", order_type="stop", quantity=10)

    def test_stop_order_zero_price_raises(self):
        with pytest.raises(ValueError, match="stop_price must be positive"):
            OrderSpec(side="sell", order_type="stop", quantity=10, stop_price=0.0)

    def test_stop_order_valid(self):
        spec = OrderSpec(side="sell", order_type="stop", quantity=10, stop_price=45.0)
        assert spec.stop_price == 45.0


class TestFillResult:
    def test_basic_construction(self):
        fill = FillResult(fill_price=100.0, fill_qty=50)
        assert fill.fill_price == 100.0
        assert fill.fill_qty == 50
        assert fill.commission == 0.0
        assert fill.slippage_bps == 0.0
        assert fill.cost_components == {}

    def test_cost_components_extensibility(self):
        fill = FillResult(
            fill_price=100.0,
            fill_qty=50,
            cost_components={"forex_carry": 0.5, "exchange_fee": 0.1},
        )
        assert fill.cost_components["forex_carry"] == 0.5
        assert fill.cost_components["exchange_fee"] == 0.1

    def test_frozen_immutability(self):
        fill = FillResult(fill_price=100.0, fill_qty=50)
        with pytest.raises(AttributeError):
            fill.fill_price = 99.0  # type: ignore[misc]


class TestMarketExecutionRouter:
    def _make_bar(self, close: float = 100.0, ts: datetime | None = None) -> pd.Series:
        data: dict = {"close": close}
        if ts is not None:
            data["timestamp"] = ts
        return pd.Series(data)

    def test_market_order_fills_at_close(self):
        router = MarketExecutionRouter()
        order = OrderSpec(side="buy", order_type="market", quantity=100)
        bar = self._make_bar(close=105.0)
        fill = router.submit(order, bar)
        assert fill is not None
        assert fill.fill_price == 105.0
        assert fill.fill_qty == 100

    def test_non_market_order_returns_none(self):
        router = MarketExecutionRouter()
        order = OrderSpec(side="buy", order_type="limit", quantity=10, limit_price=50.0)
        bar = self._make_bar(close=55.0)
        assert router.submit(order, bar) is None
