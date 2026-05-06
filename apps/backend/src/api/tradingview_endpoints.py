"""// ZeaZDev [Backend TradingView Endpoints] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import json
import os
from datetime import datetime
from logging import getLogger
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = getLogger(__name__)

router = APIRouter()

# Lazily instantiate Prisma so importing this router does not require a generated
# Prisma client. Runtime database access still fails clearly if generation has not
# been completed.
prisma: Any | None = None


class TradingViewAlert(BaseModel):
    """TradingView webhook alert payload"""

    ticker: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    exchange: str = Field(default="binance", description="Exchange name")
    action: str = Field(..., description="BUY, SELL, or CLOSE")
    price: Optional[float] = Field(None, description="Alert trigger price")
    strategy: Optional[str] = Field(None, description="Strategy name from TradingView")
    time: Optional[str] = Field(None, description="Alert timestamp")
    message: Optional[str] = Field(None, description="Custom alert message")
    # Additional fields from TradingView
    interval: Optional[str] = Field(None, description="Timeframe interval")
    volume: Optional[float] = Field(None, description="Volume at alert")
    close: Optional[float] = Field(None, description="Close price")
    open: Optional[float] = Field(None, description="Open price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")


class TradingViewWebhookConfig(BaseModel):
    """Configuration for TradingView webhook"""

    user_id: str
    webhook_secret: str
    auto_trade: bool = Field(default=False, description="Automatically execute trades")
    position_size: Optional[float] = Field(
        None, description="Position size in base currency"
    )
    risk_per_trade: Optional[float] = Field(
        default=1.0, description="Risk percentage per trade"
    )


def _get_prisma() -> Any:
    global prisma
    if prisma is None:
        from prisma import Prisma

        prisma = Prisma()
    return prisma


def _model_dump(alert: TradingViewAlert) -> dict[str, Any]:
    """Return a Pydantic v2-compatible dump with a v1 fallback."""
    if hasattr(alert, "model_dump"):
        return alert.model_dump()
    return alert.dict()


def verify_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None),
) -> str:
    """
    Verify TradingView webhook secret from header.

    Args:
        x_webhook_secret: Secret token from TradingView webhook header

    Returns:
        Validated secret

    Raises:
        HTTPException: If secret is missing or invalid
    """
    if not x_webhook_secret:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing webhook secret. Configure X-Webhook-Secret header "
                "in TradingView."
            ),
        )

    # In production, validate against stored webhook configs
    expected_secret = os.getenv("TRADINGVIEW_WEBHOOK_SECRET")
    if expected_secret and x_webhook_secret != expected_secret:
        logger.warning("Invalid webhook secret received")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    return x_webhook_secret


@router.post("/webhook")
async def tradingview_webhook(
    alert: TradingViewAlert, webhook_secret: str = Depends(verify_webhook_secret)
):
    """
    Receive TradingView webhook alerts.

    This endpoint receives alerts from TradingView and can:
    1. Log the alert for audit purposes
    2. Trigger automated trading (if configured)
    3. Send notifications via Telegram

    To configure in TradingView:
    1. Create an alert on your chart
    2. In alert settings, set Webhook URL to:
       https://your-domain.com/tradingview/webhook
    3. Add custom header: X-Webhook-Secret: your-secret-key
    4. Use JSON format in alert message with fields like:
       {"ticker": "{{ticker}}", "action": "{{strategy.order.action}}",
        "price": {{close}}, "time": "{{time}}"}

    Args:
        alert: TradingView alert payload
        webhook_secret: Validated webhook secret

    Returns:
        Success message with alert ID
    """
    try:
        # Ensure Prisma is connected
        client = _get_prisma()
        if not client.is_connected():
            await client.connect()

        # Normalize action to uppercase
        action = alert.action.upper()
        if action not in ["BUY", "SELL", "CLOSE", "HOLD"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be BUY, SELL, CLOSE, or HOLD",
            )

        payload = _model_dump(alert)

        # Store alert in database for audit trail. Field names must match the
        # Prisma schema's camelCase identifiers, and rawPayload is a string field.
        alert_record = await client.tradingviewalert.create(
            data={
                "ticker": alert.ticker,
                "exchange": alert.exchange,
                "action": action,
                "price": alert.price,
                "strategy": alert.strategy or "TRADINGVIEW_ALERT",
                "interval": alert.interval,
                "volume": alert.volume,
                "message": alert.message,
                "receivedAt": datetime.utcnow(),
                "rawPayload": json.dumps(payload, default=str),
            }
        )

        logger.info(
            f"TradingView alert received: {alert.ticker} {action} @ {alert.price}",
            extra={
                "component": "tradingview",
                "alert_id": alert_record.id,
                "ticker": alert.ticker,
                "action": action,
            },
        )

        # TODO: Implement auto-trading logic here
        # Check if user has auto_trade enabled
        # Execute trade via CCXT if configured

        return {
            "status": "success",
            "alert_id": alert_record.id,
            "message": f"Alert received: {action} {alert.ticker}",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing TradingView alert: {str(e)}",
            extra={"component": "tradingview", "error": str(e)},
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to process alert: {str(e)}"
        ) from e


@router.get("/alerts")
async def list_tradingview_alerts(
    limit: int = Query(50, ge=1, le=500),
    ticker: Optional[str] = None,
    action: Optional[str] = None,
):
    """
    List recent TradingView alerts.

    Args:
        limit: Maximum number of alerts to return (default 50)
        ticker: Filter by ticker symbol
        action: Filter by action (BUY, SELL, CLOSE)

    Returns:
        List of TradingView alerts
    """
    try:
        client = _get_prisma()
        if not client.is_connected():
            await client.connect()

        where_clause = {}
        if ticker:
            where_clause["ticker"] = ticker
        if action:
            where_clause["action"] = action.upper()

        alerts = await client.tradingviewalert.find_many(
            where=where_clause, order={"receivedAt": "desc"}, take=limit
        )

        return {
            "alerts": [
                {
                    "id": alert.id,
                    "ticker": alert.ticker,
                    "exchange": alert.exchange,
                    "action": alert.action,
                    "price": alert.price,
                    "strategy": alert.strategy,
                    "interval": alert.interval,
                    "message": alert.message,
                    "received_at": (
                        alert.receivedAt.isoformat() if alert.receivedAt else None
                    ),
                }
                for alert in alerts
            ],
            "count": len(alerts),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching TradingView alerts: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch alerts: {str(e)}"
        ) from e


@router.get("/config")
async def get_webhook_config():
    """
    Get TradingView webhook configuration instructions.

    Returns:
        Configuration guide and webhook URL
    """
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    webhook_url = f"{base_url}/tradingview/webhook"

    return {
        "webhook_url": webhook_url,
        "setup_instructions": {
            "step_1": "Create an alert in TradingView on your desired chart/indicator",
            "step_2": f"Set Webhook URL to: {webhook_url}",
            "step_3": "Add custom header: X-Webhook-Secret: your-secret-key",
            "step_4": "Configure alert message in JSON format",
            "example_message": {
                "ticker": "{{ticker}}",
                "action": "BUY",
                "price": "{{close}}",
                "time": "{{time}}",
                "interval": "{{interval}}",
                "strategy": "My TradingView Strategy",
            },
            "supported_actions": ["BUY", "SELL", "CLOSE", "HOLD"],
        },
        "environment_variables": {
            "TRADINGVIEW_WEBHOOK_SECRET": (
                "Set this in your .env file for webhook authentication"
            )
        },
    }
