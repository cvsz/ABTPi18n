"""// ZeaZDev [Portfolio Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import ccxt
from prisma import Prisma

from src.security.crypto_service import decrypt_data

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service for aggregating and managing multi-account portfolios"""

    def __init__(self):
        self.prisma = Prisma()
        self.exchanges_cache: Dict[int, ccxt.Exchange] = {}

    async def create_account(
        self,
        user_id: int,
        exchange_key_id: int,
        label: str,
        group: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new account for portfolio tracking"""
        await self.prisma.connect()

        try:
            # Verify exchange key exists and belongs to user
            exchange_key = await self.prisma.exchangekey.find_first(
                where={"id": exchange_key_id, "ownerId": user_id}
            )

            if not exchange_key:
                raise ValueError("Exchange key not found or does not belong to user")

            # Create account
            account = await self.prisma.account.create(
                data={
                    "userId": user_id,
                    "exchangeKeyId": exchange_key_id,
                    "label": label,
                    "group": group,
                    "enabled": True,
                }
            )

            return {
                "id": account.id,
                "label": account.label,
                "exchange": exchange_key.exchange,
                "group": account.group,
                "enabled": account.enabled,
            }
        finally:
            await self.prisma.disconnect()

    async def list_accounts(self, user_id: int) -> List[Dict[str, Any]]:
        """List all accounts for a user"""
        await self.prisma.connect()

        try:
            accounts = await self.prisma.account.find_many(
                where={"userId": user_id}, include={"exchangeKey": True}
            )

            return [
                {
                    "id": acc.id,
                    "label": acc.label,
                    "exchange": acc.exchangeKey.exchange,
                    "group": acc.group,
                    "enabled": acc.enabled,
                    "created_at": acc.createdAt.isoformat(),
                }
                for acc in accounts
            ]
        finally:
            await self.prisma.disconnect()

    async def sync_account_positions(self, account_id: int) -> List[Dict[str, Any]]:
        """Sync positions from exchange for a specific account"""
        await self.prisma.connect()

        try:
            # Get account with exchange key
            account = await self.prisma.account.find_first(
                where={"id": account_id}, include={"exchangeKey": True}
            )

            if not account or not account.enabled:
                return []

            # Get or create exchange instance
            exchange = await self._get_exchange_instance(account.exchangeKey)

            # Fetch positions from exchange
            try:
                balance = await asyncio.to_thread(exchange.fetch_balance)
                positions = []

                for symbol, amount in balance["total"].items():
                    if amount > 0:
                        # Try to get current price
                        try:
                            ticker_symbol = f"{symbol}/USDT"
                            ticker = await asyncio.to_thread(
                                exchange.fetch_ticker, ticker_symbol
                            )
                            current_price = ticker["last"]
                        except Exception as e:
                            logger.debug(f"Ticker fetch failed for {symbol}: {e}")
                            current_price = None

                        # Update or create position in database
                        existing = await self.prisma.position.find_first(
                            where={"accountId": account_id, "symbol": symbol}
                        )

                        if existing:
                            await self.prisma.position.update(
                                where={"id": existing.id},
                                data={
                                    "quantity": amount,
                                    "currentPrice": current_price,
                                },
                            )
                        else:
                            await self.prisma.position.create(
                                data={
                                    "accountId": account_id,
                                    "symbol": symbol,
                                    "side": "LONG",
                                    "quantity": amount,
                                    "entryPrice": current_price or 0,
                                    "currentPrice": current_price,
                                }
                            )

                        positions.append(
                            {
                                "symbol": symbol,
                                "quantity": amount,
                                "current_price": current_price,
                            }
                        )

                return positions
            except Exception as e:
                logger.error(f"Failed to sync positions for account {account_id}: {e}")
                return []
        finally:
            await self.prisma.disconnect()

    async def get_portfolio_summary(self, user_id: int) -> Dict[str, Any]:
        """Get aggregated portfolio summary across all accounts"""
        await self.prisma.connect()

        try:
            # Get all enabled accounts
            accounts = await self.prisma.account.find_many(
                where={"userId": user_id, "enabled": True},
                include={"positions": True, "exchangeKey": True},
            )

            # Aggregate positions
            aggregated_positions: Dict[str, Dict[str, Any]] = {}
            total_value_usd = 0.0

            for account in accounts:
                for position in account.positions:
                    symbol = position.symbol

                    if symbol not in aggregated_positions:
                        aggregated_positions[symbol] = {
                            "symbol": symbol,
                            "total_quantity": 0.0,
                            "accounts": [],
                        }

                    aggregated_positions[symbol]["total_quantity"] += position.quantity
                    aggregated_positions[symbol]["accounts"].append(
                        {
                            "account_id": account.id,
                            "account_label": account.label,
                            "quantity": position.quantity,
                            "current_price": position.currentPrice,
                        }
                    )

                    # Add to total value
                    if position.currentPrice:
                        total_value_usd += position.quantity * position.currentPrice

            # Get total PnL from trade logs
            trade_logs = await self.prisma.tradelog.find_many(
                where={"botRun": {"userId": user_id}}
            )
            total_pnl = sum(t.pnl for t in trade_logs)

            return {
                "total_accounts": len(accounts),
                "total_positions": len(aggregated_positions),
                "total_value_usd": round(total_value_usd, 2),
                "total_pnl": round(total_pnl, 4),
                "positions": list(aggregated_positions.values()),
                "last_updated": datetime.utcnow().isoformat(),
            }
        finally:
            await self.prisma.disconnect()

    async def get_account_performance(self, account_id: int) -> Dict[str, Any]:
        """Get performance metrics for a specific account"""
        await self.prisma.connect()

        try:
            # Get account positions
            positions = await self.prisma.position.find_many(
                where={"accountId": account_id}
            )

            # Calculate metrics
            total_positions = len(positions)
            total_pnl = sum(p.pnl for p in positions)

            # Get account value
            account_value = sum(p.quantity * (p.currentPrice or 0) for p in positions)

            return {
                "account_id": account_id,
                "total_positions": total_positions,
                "account_value_usd": round(account_value, 2),
                "total_pnl": round(total_pnl, 4),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "quantity": p.quantity,
                        "entry_price": p.entryPrice,
                        "current_price": p.currentPrice,
                        "pnl": p.pnl,
                    }
                    for p in positions
                ],
            }
        finally:
            await self.prisma.disconnect()

    async def _get_exchange_instance(self, exchange_key) -> ccxt.Exchange:
        """Get or create CCXT exchange instance"""
        if exchange_key.id in self.exchanges_cache:
            return self.exchanges_cache[exchange_key.id]

        # Decrypt keys
        api_key = decrypt_data(exchange_key.encrypted_key, exchange_key.iv_key)
        api_secret = decrypt_data(exchange_key.encrypted_secret, exchange_key.iv_secret)

        # Create exchange instance
        exchange_class = getattr(ccxt, exchange_key.exchange)
        exchange = exchange_class(
            {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}
        )

        # Cache instance
        self.exchanges_cache[exchange_key.id] = exchange

        return exchange

    async def delete_account(self, account_id: int, user_id: int) -> Dict[str, Any]:
        """Delete an account and its positions"""
        await self.prisma.connect()

        try:
            # Verify account belongs to user
            account = await self.prisma.account.find_first(
                where={"id": account_id, "userId": user_id}
            )

            if not account:
                raise ValueError("Account not found or does not belong to user")

            # Delete all positions for this account
            await self.prisma.position.delete_many(where={"accountId": account_id})

            # Delete account
            await self.prisma.account.delete(where={"id": account_id})

            return {"success": True, "account_id": account_id}
        finally:
            await self.prisma.disconnect()
