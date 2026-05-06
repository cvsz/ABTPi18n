from __future__ import annotations

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOT_", extra="ignore")

    binance_api_key: SecretStr = Field(..., description="Binance Futures API key")
    binance_api_secret: SecretStr = Field(..., description="Binance Futures API secret")
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT:USDT", "ETH/USDT:USDT"])
    fixed_notional_usdt: float = Field(default=100.0, gt=0)
    max_correlation: float = Field(default=0.65, gt=0, lt=1)
    websocket_timeout_seconds: float = Field(default=30.0, gt=0)
    heartbeat_interval_seconds: float = Field(default=15.0, gt=0)
    max_reconnect_backoff_seconds: float = Field(default=60.0, gt=1)
    internal_port: int = Field(default=22022, description="Spaceship Standard port for internal comms or SSH tunnels")
    leverage: int = Field(default=3, ge=1, le=20)
    database_url: PostgresDsn = Field(default="postgresql://postgres:postgres@postgres:5432/abtp")
    ml_model_path: str = Field(default="/models/xgb_trade_gate.json")
    dry_run: bool = True


class AllocationConfig(BaseSettings):
    scalp: float = 0.20
    swing: float = 0.30
    position: float = 0.50
