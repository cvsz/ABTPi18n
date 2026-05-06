from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import ccxt.pro as ccxtpro

from binance_perp_bot.config import BotConfig
from binance_perp_bot.models import MarketSnapshot, PositionIntent

SnapshotHandler = Callable[[MarketSnapshot], Awaitable[None]]


class BinancePerpStream:
    def __init__(self, config: BotConfig, on_snapshot: SnapshotHandler) -> None:
        self.config = config
        self.on_snapshot = on_snapshot
        self.exchange = ccxtpro.binanceusdm(
            {
                "apiKey": config.binance_api_key.get_secret_value(),
                "secret": config.binance_api_secret.get_secret_value(),
                "enableRateLimit": True,
                "options": {"defaultType": "swap", "adjustForTimeDifference": True},
            }
        )
        self.logger = logging.getLogger(__name__)
        self._stopping = asyncio.Event()

    async def close(self) -> None:
        self._stopping.set()
        await self.exchange.close()

    async def stream_symbol(self, symbol: str, timeframe: str) -> None:
        backoff = 1.0
        while not self._stopping.is_set():
            heartbeat_task = asyncio.create_task(self._heartbeat(symbol))
            try:
                await self.exchange.load_markets()
                while not self._stopping.is_set():
                    if heartbeat_task.done():
                        heartbeat_task.result()
                    orderbook_task = asyncio.create_task(self.exchange.watch_order_book(symbol, limit=20))
                    ticker_task = asyncio.create_task(self.exchange.watch_ticker(symbol))
                    done, pending = await asyncio.wait(
                        {orderbook_task, ticker_task},
                        timeout=self.config.websocket_timeout_seconds,
                        return_when=asyncio.ALL_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    if pending or len(done) != 2:
                        raise TimeoutError(f"WebSocket stalled for {symbol}")
                    orderbook = orderbook_task.result()
                    ticker = ticker_task.result()
                    ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=250)
                    await self.on_snapshot(MarketSnapshot(symbol, timeframe, ohlcv, ticker, orderbook))
                    backoff = 1.0
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as exc:
                self.logger.warning("websocket_reconnect", extra={"symbol": symbol, "trace_id": "stream", "strategy": timeframe}, exc_info=exc)
                await self._recreate_exchange()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, self.config.max_reconnect_backoff_seconds)
            finally:
                heartbeat_task.cancel()

    async def _heartbeat(self, symbol: str) -> None:
        while not self._stopping.is_set():
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
            await asyncio.wait_for(self.exchange.fetch_time(), timeout=10)
            self.logger.info("websocket_heartbeat_ok", extra={"symbol": symbol, "trace_id": "heartbeat", "strategy": "stream"})

    async def _recreate_exchange(self) -> None:
        await self.exchange.close()
        self.exchange = ccxtpro.binanceusdm(
            {
                "apiKey": self.config.binance_api_key.get_secret_value(),
                "secret": self.config.binance_api_secret.get_secret_value(),
                "enableRateLimit": True,
                "options": {"defaultType": "swap", "adjustForTimeDifference": True},
            }
        )

    async def fetch_equity_usdt(self) -> float:
        balance = await self.exchange.fetch_balance({"type": "swap"})
        return float(balance["USDT"]["total"])

    async def execute(self, intent: PositionIntent) -> dict[str, Any]:
        if self.config.dry_run:
            return {"id": f"dry-{intent.signal.trace_id}", "average": intent.signal.metadata.get("price"), "status": "closed"}
        return await self.exchange.create_order(
            intent.signal.symbol,
            "market",
            intent.side.value,
            intent.amount,
            None,
            {"reduceOnly": intent.reduce_only, "leverage": intent.leverage},
        )
