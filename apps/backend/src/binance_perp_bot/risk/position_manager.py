from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Protocol

import numpy as np
from binance_perp_bot.models import (
    OpenPosition,
    PositionIntent,
    Side,
    SignalAction,
    StrategyKind,
    TradeSignal,
)


class AllocationConfigLike(Protocol):
    scalp: float
    swing: float
    position: float


class PositionManager:
    def __init__(
        self, allocation: AllocationConfigLike, max_correlation: float
    ) -> None:
        self._allocation = allocation
        self._max_correlation = max_correlation
        self._equity_usdt = 0.0
        self._reserved_usdt = 0.0
        self._positions: dict[str, OpenPosition] = {}
        self._return_history: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    async def update_equity(self, equity_usdt: float) -> None:
        async with self._lock:
            self._equity_usdt = equity_usdt

    async def set_return_history(self, symbol: str, returns: np.ndarray) -> None:
        async with self._lock:
            self._return_history[symbol] = returns

    async def reserve(
        self, signal: TradeSignal, price: float, leverage: int
    ) -> PositionIntent | None:
        if signal.action not in {SignalAction.ENTER_LONG, SignalAction.ENTER_SHORT}:
            return None
        async with self._lock:
            if self._portfolio_correlation(signal.symbol) > self._max_correlation:
                return None
            heatmap = self._heatmap_locked()
            allocation_cap = (
                self._equity_usdt
                * self._target_allocation(signal.strategy)
                * heatmap[signal.strategy]
            )
            used = sum(
                p.notional_usdt
                for p in self._positions.values()
                if p.strategy == signal.strategy
            )
            available = min(
                self._equity_usdt - self._reserved_usdt, allocation_cap - used
            )
            notional = min(signal.size_usdt, max(0.0, available))
            if notional <= 0:
                return None
            self._reserved_usdt += notional
            side = Side.BUY if signal.action == SignalAction.ENTER_LONG else Side.SELL
            amount = notional * leverage / price
            return PositionIntent(signal, side, amount, notional, leverage)

    async def commit_open(self, intent: PositionIntent, fill_price: float) -> None:
        async with self._lock:
            key = (
                f"{intent.signal.strategy}:{intent.signal.symbol}:"
                f"{intent.signal.trace_id}"
            )
            self._positions[key] = OpenPosition(
                symbol=intent.signal.symbol,
                strategy=intent.signal.strategy,
                notional_usdt=intent.notional_usdt,
                side=intent.side,
                entry_price=fill_price,
                amount=intent.amount,
                trace_id=intent.signal.trace_id,
            )
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)

    async def release(self, intent: PositionIntent) -> None:
        async with self._lock:
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)

    def _target_allocation(self, strategy: StrategyKind) -> float:
        return {
            StrategyKind.SCALP: self._allocation.scalp,
            StrategyKind.SWING: self._allocation.swing,
            StrategyKind.POSITION: self._allocation.position,
        }[strategy]

    def _heatmap_locked(self) -> dict[StrategyKind, float]:
        exposure = defaultdict(float)
        for position in self._positions.values():
            exposure[position.strategy] += position.notional_usdt
        total = sum(exposure.values()) or 1.0
        return {
            kind: max(
                0.50,
                min(
                    1.25, 1.0 - (exposure[kind] / total - self._target_allocation(kind))
                ),
            )
            for kind in StrategyKind
        }

    def _portfolio_correlation(self, symbol: str) -> float:
        incoming = self._return_history.get(symbol)
        if incoming is None or incoming.size < 20 or not self._positions:
            return 0.0
        correlations = []
        for position in self._positions.values():
            existing = self._return_history.get(position.symbol)
            if existing is None or existing.size != incoming.size:
                continue
            corr = np.corrcoef(incoming, existing)[0, 1]
            if np.isfinite(corr):
                correlations.append(abs(float(corr)))
        return max(correlations, default=0.0)
