from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalAction(str, Enum):
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    HOLD = "hold"


class RegimeMode(str, Enum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    HIGH_VOLATILITY = "high_volatility"


class StrategyKind(str, Enum):
    SCALP = "scalp"
    SWING = "swing"
    POSITION = "position"


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    timeframe: str
    ohlcv: list[list[float]]
    ticker: dict[str, Any]
    orderbook: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TradeSignal:
    symbol: str
    strategy: StrategyKind
    action: SignalAction
    confidence: float
    size_usdt: float
    regime: RegimeMode
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionIntent:
    signal: TradeSignal
    side: Side
    amount: float
    notional_usdt: float
    leverage: int
    reduce_only: bool = False


@dataclass
class OpenPosition:
    symbol: str
    strategy: StrategyKind
    notional_usdt: float
    side: Side
    entry_price: float
    amount: float
    trace_id: str
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
