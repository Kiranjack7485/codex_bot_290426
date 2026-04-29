from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


def _get_env_list(name: str, default: str) -> List[str]:
    value = os.getenv(name, default)
    return [item.strip().upper() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class StrategyConfig:
    primary_timeframe: str = "5m"
    confirmation_timeframe: str = "15m"
    swing_lookback: int = 2
    structure_swings: int = 6
    equal_level_tolerance_bps: float = 8.0
    volume_ma_period: int = 20
    volume_spike_factor: float = 1.5
    fvg_fill_tolerance_bps: float = 15.0
    break_retest_tolerance_bps: float = 10.0
    pullback_ema_tolerance_bps: float = 12.0
    ohlcv_limit: int = 300
    session_timezone: str = "Asia/Kolkata"
    session_windows: dict = field(
        default_factory=lambda: {
            "Indian Session": ("09:00", "12:30"),
            "US/London Overlap": ("18:30", "22:30"),
        }
    )

    @classmethod
    def from_env(cls) -> "StrategyConfig":
        return cls(
            swing_lookback=int(os.getenv("BOT_SWING_LOOKBACK", "2")),
            structure_swings=int(os.getenv("BOT_STRUCTURE_SWINGS", "6")),
            equal_level_tolerance_bps=float(os.getenv("BOT_EQUAL_LEVEL_TOLERANCE_BPS", "8")),
            volume_ma_period=int(os.getenv("BOT_VOLUME_MA_PERIOD", "20")),
            volume_spike_factor=float(os.getenv("BOT_VOLUME_SPIKE_FACTOR", "1.5")),
            fvg_fill_tolerance_bps=float(os.getenv("BOT_FVG_FILL_TOLERANCE_BPS", "15")),
            break_retest_tolerance_bps=float(os.getenv("BOT_BREAK_RETEST_TOLERANCE_BPS", "10")),
            pullback_ema_tolerance_bps=float(os.getenv("BOT_PULLBACK_EMA_TOLERANCE_BPS", "12")),
        )


@dataclass(slots=True)
class RiskConfig:
    max_active_trades: int = 2
    capital_usage_per_trade: float = 0.4
    capital_buffer: float = 0.2
    risk_per_trade: float = 0.01
    min_rr: float = 1.5
    ideal_rr: float = 2.0
    default_leverage: int = 5

    @classmethod
    def from_env(cls) -> "RiskConfig":
        return cls(
            max_active_trades=int(os.getenv("BOT_MAX_ACTIVE_TRADES", "2")),
            capital_usage_per_trade=float(os.getenv("BOT_CAPITAL_USAGE_PER_TRADE", "0.4")),
            capital_buffer=float(os.getenv("BOT_CAPITAL_BUFFER", "0.2")),
            risk_per_trade=float(os.getenv("BOT_RISK_PER_TRADE", "0.01")),
            min_rr=float(os.getenv("BOT_MIN_RR", "1.5")),
            ideal_rr=float(os.getenv("BOT_IDEAL_RR", "2.0")),
            default_leverage=int(os.getenv("BOT_LEVERAGE", "5")),
        )


@dataclass(slots=True)
class AppConfig:
    real_api_key: str
    real_api_secret: str
    testnet_api_key: str
    testnet_api_secret: str
    telegram_bot_token: str
    telegram_chat_id: str
    symbols: List[str]
    scan_interval_seconds: int
    strategy: StrategyConfig
    risk: RiskConfig

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv()

        required = {
            "BINANCE_API_KEY": os.getenv("BINANCE_API_KEY"),
            "BINANCE_SECRET": os.getenv("BINANCE_SECRET"),
            "BINANCE_TESTNET_API_KEY": os.getenv("BINANCE_TESTNET_API_KEY"),
            "BINANCE_TESTNET_SECRET": os.getenv("BINANCE_TESTNET_SECRET"),
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        strategy = StrategyConfig.from_env()
        risk = RiskConfig.from_env()
        if risk.capital_usage_per_trade * risk.max_active_trades + risk.capital_buffer > 1:
            raise ValueError("Capital usage and buffer exceed total account capital.")
        if risk.min_rr < 1.5 or risk.ideal_rr < risk.min_rr:
            raise ValueError("Risk/reward configuration violates minimum strategy requirements.")

        return cls(
            real_api_key=required["BINANCE_API_KEY"] or "",
            real_api_secret=required["BINANCE_SECRET"] or "",
            testnet_api_key=required["BINANCE_TESTNET_API_KEY"] or "",
            testnet_api_secret=required["BINANCE_TESTNET_SECRET"] or "",
            telegram_bot_token=required["TELEGRAM_BOT_TOKEN"] or "",
            telegram_chat_id=required["TELEGRAM_CHAT_ID"] or "",
            symbols=_get_env_list("BOT_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"),
            scan_interval_seconds=int(os.getenv("BOT_SCAN_INTERVAL_SECONDS", "60")),
            strategy=strategy,
            risk=risk,
        )
