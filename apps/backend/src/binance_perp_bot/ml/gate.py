from __future__ import annotations

from pathlib import Path

import numpy as np
import xgboost as xgb

from binance_perp_bot.indicators import adx, atr, closes, ema, rsi
from binance_perp_bot.models import MarketSnapshot, TradeSignal


class XGBoostTradeGate:
    def __init__(self, model_path: str, threshold: float = 0.55) -> None:
        self.threshold = threshold
        self.model = xgb.Booster()
        self.model.load_model(str(Path(model_path)))

    def features(self, snapshot: MarketSnapshot, signal: TradeSignal) -> np.ndarray:
        price = closes(snapshot.ohlcv)
        last = price[-1]
        feature_row = np.asarray(
            [
                signal.confidence,
                atr(snapshot.ohlcv) / max(last, 1e-9),
                adx(snapshot.ohlcv),
                rsi(price, 14),
                (ema(price, 12) - ema(price, 26)) / max(last, 1e-9),
                float(signal.action.value == "enter_long"),
                float(signal.regime.value == "trend"),
                float(signal.regime.value == "mean_reversion"),
            ],
            dtype=float,
        )
        return feature_row.reshape(1, -1)

    def allow(self, snapshot: MarketSnapshot, signal: TradeSignal) -> bool:
        matrix = xgb.DMatrix(self.features(snapshot, signal))
        probability = float(self.model.predict(matrix)[0])
        signal.metadata["xgb_trade_probability"] = probability
        return probability >= self.threshold
