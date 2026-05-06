from __future__ import annotations

import asyncio

import numpy as np
from binance_perp_bot.models import (
    MarketSnapshot,
    RegimeMode,
    SignalAction,
    StrategyKind,
    TradeSignal,
)
from binance_perp_bot.risk.position_manager import PositionManager
from binance_perp_bot.strategies import (
    BaseStrategy,
    PositionStrategy,
    ScalpStrategy,
    SwingStrategy,
)


class Allocation:
    scalp = 0.20
    swing = 0.30
    position = 0.50


def candles(count: int = 250) -> list[list[float]]:
    return [
        [i * 60_000, 100 + i * 0.1, 101 + i * 0.1, 99 + i * 0.1, 100 + i * 0.1, 10]
        for i in range(count)
    ]


def snapshot(symbol: str = "BTC/USDT:USDT") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        timeframe="1m",
        ohlcv=candles(),
        ticker={"last": 125.0},
        orderbook={},
    )


def test_concrete_strategies_implement_base_contract() -> None:
    for strategy in (ScalpStrategy(), SwingStrategy(), PositionStrategy()):
        assert isinstance(strategy, BaseStrategy)
        assert strategy.calculate_size(snapshot(), 1_000, 100) > 0
        assert 0 <= strategy.get_regime_suitability(RegimeMode.TREND) <= 1


def test_position_manager_rejects_high_correlation() -> None:
    async def scenario() -> None:
        manager = PositionManager(Allocation(), max_correlation=0.65)
        await manager.update_equity(1_000)
        returns = np.linspace(-0.01, 0.01, 30)
        await manager.set_return_history("BTC/USDT:USDT", returns)
        await manager.set_return_history("ETH/USDT:USDT", returns)
        signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        first = await manager.reserve(signal, 100, 3)
        assert first is not None
        await manager.commit_open(first, 100)
        correlated = TradeSignal(
            "ETH/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        assert await manager.reserve(correlated, 100, 3) is None

    asyncio.run(scenario())


def test_position_manager_rejects_duplicate_symbol_atomically() -> None:
    async def scenario() -> None:
        manager = PositionManager(Allocation(), max_correlation=0.65, max_positions=1)
        await manager.update_equity(1_000)
        signal = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SCALP,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        first = await manager.reserve(signal, 100, 3)
        assert first is not None
        await manager.commit_open(first, 100)

        duplicate = TradeSignal(
            "BTC/USDT:USDT",
            StrategyKind.SWING,
            SignalAction.ENTER_LONG,
            0.9,
            100,
            RegimeMode.TREND,
        )
        assert await manager.reserve(duplicate, 100, 3) is None
        assert len(await manager.positions()) == 1

    asyncio.run(scenario())
