from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from binance_perp_bot.config import AllocationConfig, BotConfig
from binance_perp_bot.db.timescale import TimescaleJournal
from binance_perp_bot.execution.engine import ExecutionEngine
from binance_perp_bot.execution.exchange import BinancePerpStream
from binance_perp_bot.ml.gate import XGBoostTradeGate
from binance_perp_bot.ml.regime import ADXRegimeDetector
from binance_perp_bot.models import MarketSnapshot
from binance_perp_bot.risk.position_manager import PositionManager
from binance_perp_bot.strategies.factory import StrategyFactory
from binance_perp_bot.utils.logging import configure_json_logging


class SnapshotDispatcher:
    def __init__(self) -> None:
        self.handler: Callable[[MarketSnapshot], Awaitable[None]] | None = None

    async def __call__(self, snapshot: MarketSnapshot) -> None:
        if self.handler is None:
            return
        await self.handler(snapshot)


async def run() -> None:
    configure_json_logging()
    config = BotConfig()
    dispatcher = SnapshotDispatcher()
    stream = BinancePerpStream(config, dispatcher)
    journal = TimescaleJournal(str(config.database_url))
    await journal.migrate()
    engine = ExecutionEngine(
        config=config,
        stream=stream,
        factory=StrategyFactory(),
        position_manager=PositionManager(AllocationConfig(), config.max_correlation),
        regime_detector=ADXRegimeDetector(),
        trade_gate=XGBoostTradeGate(config.ml_model_path),
        journal=journal,
    )
    dispatcher.handler = engine.on_snapshot
    tasks = [
        asyncio.create_task(stream.stream_symbol(symbol, timeframe))
        for symbol in config.symbols
        for timeframe in ("1m", "5m", "4h", "1d", "1w")
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await stream.close()


if __name__ == "__main__":
    asyncio.run(run())
