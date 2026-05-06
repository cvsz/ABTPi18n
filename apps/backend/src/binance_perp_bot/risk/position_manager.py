from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Protocol

import numpy as np
from binance_perp_bot.models import (
    Position,
    PositionIntent,
    RegimeMode,
    Side,
    SignalAction,
    StrategyKind,
    TradeSignal,
)
from binance_perp_bot.risk.risk_engine import RiskEngine


class AllocationConfigLike(Protocol):
    scalp: float
    swing: float
    position: float


class PositionManager:
    """Atomic single source of truth for shared-capital open positions."""

    def __init__(
        self,
        allocation: AllocationConfigLike,
        max_correlation: float,
        max_positions: int = 30,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self._allocation = allocation
        self._max_correlation = max_correlation
        self._max_positions = max_positions
        self._equity_usdt = 0.0
        self._reserved_usdt = 0.0
        self._positions: dict[str, Position] = {}
        self._return_history: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()
        self.risk_engine = risk_engine or RiskEngine(max_correlation)
        self.logger = logging.getLogger("PositionManager")

    @property
    def total_equity(self) -> float:
        return self._equity_usdt

    @property
    def used_margin(self) -> float:
        return sum(position.margin_used for position in self._positions.values())

    @property
    def current_exposure(self) -> float:
        return sum(position.notional_value for position in self._positions.values())

    async def update_equity(self, equity_usdt: float) -> None:
        async with self._lock:
            self._equity_usdt = equity_usdt

    async def set_return_history(self, symbol: str, returns: np.ndarray) -> None:
        async with self._lock:
            self._return_history[symbol] = returns
            prices = np.cumprod(1.0 + returns)
            self.risk_engine.set_price_history(symbol, prices)

    async def positions(self) -> list[Position]:
        async with self._lock:
            return list(self._positions.values())

    async def can_open_new_position(self) -> bool:
        async with self._lock:
            return self._can_open_new_position_locked()

    async def open_position(self, position: Position) -> bool:
        async with self._lock:
            if not self._can_open_new_position_locked():
                self.logger.warning(
                    "max_positions_reached",
                    extra={
                        "trace_id": position.trace_id,
                        "symbol": position.symbol,
                        "max_positions": self._max_positions,
                    },
                )
                return False
            if any(
                existing.symbol == position.symbol
                for existing in self._positions.values()
            ):
                self.logger.warning(
                    "duplicate_symbol_position_rejected",
                    extra={"trace_id": position.trace_id, "symbol": position.symbol},
                )
                return False
            self._positions[position.id] = position
            self.logger.info(
                "position_registered",
                extra={
                    "trace_id": position.trace_id,
                    "symbol": position.symbol,
                    "side": position.side,
                },
            )
            return True

    async def close_position(
        self, position_id: str, exit_price: float, trace_id: str
    ) -> Position | None:
        async with self._lock:
            position = self._positions.pop(position_id, None)
            if position is not None:
                self.logger.info(
                    "position_closed",
                    extra={
                        "trace_id": trace_id,
                        "symbol": position.symbol,
                        "exit_price": exit_price,
                    },
                )
            return position

    async def reserve(
        self, signal: TradeSignal, price: float, leverage: int
    ) -> PositionIntent | None:
        if signal.action not in {SignalAction.ENTER_LONG, SignalAction.ENTER_SHORT}:
            return None
        async with self._lock:
            side = "LONG" if signal.action == SignalAction.ENTER_LONG else "SHORT"
            if not self._can_open_new_position_locked():
                self.logger.warning(
                    "max_positions_reached",
                    extra={
                        "trace_id": signal.trace_id,
                        "symbol": signal.symbol,
                        "max_positions": self._max_positions,
                    },
                )
                return None
            if any(
                position.symbol == signal.symbol
                for position in self._positions.values()
            ):
                self.logger.warning(
                    "duplicate_symbol_position_rejected",
                    extra={"trace_id": signal.trace_id, "symbol": signal.symbol},
                )
                return None
            if not self.risk_engine.resolve_conflict(
                side, self._positions.values(), signal.symbol
            ):
                return None
            if not self.risk_engine.check_correlation(
                signal.symbol, self._positions.values()
            ):
                return None
            if self._portfolio_correlation(signal.symbol) > self._max_correlation:
                return None
            heatmap = self._heatmap_locked()
            allocation_cap = (
                self._equity_usdt
                * self._target_allocation(signal.strategy)
                * heatmap[signal.strategy]
            )
            used = sum(
                p.margin_used
                for p in self._positions.values()
                if p.strategy_kind == signal.strategy
            )
            available = min(
                self._equity_usdt - self._reserved_usdt - self.used_margin,
                allocation_cap - used,
            )
            margin = min(signal.size_usdt, max(0.0, available))
            if margin <= 0:
                return None
            self._reserved_usdt += margin
            order_side = (
                Side.BUY if signal.action == SignalAction.ENTER_LONG else Side.SELL
            )
            amount = margin * leverage / price
            return PositionIntent(signal, order_side, amount, margin, leverage)

    async def commit_open(self, intent: PositionIntent, fill_price: float) -> None:
        side = "LONG" if intent.side == Side.BUY else "SHORT"
        regime = intent.signal.regime
        position = Position(
            strategy_id=intent.signal.strategy.value,
            symbol=intent.signal.symbol,
            side=side,
            size=intent.amount,
            entry_price=fill_price,
            leverage=intent.leverage,
            margin_used=intent.notional_usdt,
            regime_at_open=(
                regime.value if isinstance(regime, RegimeMode) else str(regime)
            ),
            trace_id=intent.signal.trace_id,
        )
        async with self._lock:
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)
        opened = await self.open_position(position)
        if not opened:
            self.logger.warning(
                "position_commit_rejected_after_fill",
                extra={
                    "trace_id": intent.signal.trace_id,
                    "symbol": intent.signal.symbol,
                },
            )

    async def release(self, intent: PositionIntent) -> None:
        async with self._lock:
            self._reserved_usdt = max(0.0, self._reserved_usdt - intent.notional_usdt)

    def get_portfolio_heatmap(self) -> dict[str, float]:
        total = (
            sum(position.margin_used for position in self._positions.values()) or 1.0
        )
        return {
            position.symbol: position.margin_used / total
            for position in self._positions.values()
        }

    def _can_open_new_position_locked(self) -> bool:
        return len(self._positions) < self._max_positions

    def _target_allocation(self, strategy: StrategyKind) -> float:
        return {
            StrategyKind.SCALP: self._allocation.scalp,
            StrategyKind.SWING: self._allocation.swing,
            StrategyKind.POSITION: self._allocation.position,
        }[strategy]

    def _heatmap_locked(self) -> dict[StrategyKind, float]:
        exposure = defaultdict(float)
        for position in self._positions.values():
            kind = position.strategy_kind
            if kind is not None:
                exposure[kind] += position.margin_used
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
