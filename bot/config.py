from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: str) -> List[str]:
    value = os.getenv(name, default)
    return [item.strip().upper() for item in value.split(",") if item.strip()]


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    token: str
    chat_id: str
    enabled: bool

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        enabled = _get_bool("TELEGRAM_ENABLED", bool(token and chat_id))
        return cls(token=token, chat_id=chat_id, enabled=enabled)


@dataclass(frozen=True, slots=True)
class CryptoConfig:
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"])
    primary_timeframe: str = "5m"
    confirmation_timeframe: str = "15m"
    ohlcv_limit: int = 300
    swing_lookback: int = 2
    structure_swings: int = 6
    equal_level_tolerance_bps: float = 8.0
    volume_ma_period: int = 20
    volume_spike_factor: float = 1.5
    fvg_fill_tolerance_bps: float = 15.0
    break_retest_tolerance_bps: float = 10.0
    pullback_ema_tolerance_bps: float = 12.0
    min_signal_score: int = 7

    @classmethod
    def from_env(cls) -> "CryptoConfig":
        return cls(
            symbols=_get_list("CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"),
            primary_timeframe=os.getenv("CRYPTO_PRIMARY_TIMEFRAME", "5m"),
            confirmation_timeframe=os.getenv("CRYPTO_CONFIRMATION_TIMEFRAME", "15m"),
            ohlcv_limit=int(os.getenv("CRYPTO_OHLCV_LIMIT", "300")),
            volume_ma_period=int(os.getenv("CRYPTO_VOLUME_MA_PERIOD", "20")),
            volume_spike_factor=float(os.getenv("CRYPTO_VOLUME_SPIKE_FACTOR", "1.5")),
            swing_lookback=int(os.getenv("CRYPTO_SWING_LOOKBACK", "2")),
            structure_swings=int(os.getenv("CRYPTO_STRUCTURE_SWINGS", "6")),
            equal_level_tolerance_bps=float(os.getenv("CRYPTO_EQUAL_LEVEL_TOLERANCE_BPS", "8")),
            fvg_fill_tolerance_bps=float(os.getenv("CRYPTO_FVG_FILL_TOLERANCE_BPS", "15")),
            break_retest_tolerance_bps=float(os.getenv("CRYPTO_BREAK_RETEST_TOLERANCE_BPS", "10")),
            pullback_ema_tolerance_bps=float(os.getenv("CRYPTO_PULLBACK_EMA_TOLERANCE_BPS", "12")),
            min_signal_score=int(os.getenv("CRYPTO_MIN_SIGNAL_SCORE", "7")),
        )


@dataclass(frozen=True, slots=True)
class SessionConfig:
    timezone: str = "Asia/Kolkata"
    india_crypto_start: str = "09:15"
    india_crypto_end: str = "10:30"
    overlap_start: str = "18:30"
    overlap_end: str = "22:30"
    india_crypto_poll_interval_seconds: int = 30
    overlap_poll_interval_seconds: int = 15
    idle_sleep_seconds: int = 45
    india_crypto_min_alert_score: int = 9
    overlap_min_alert_score: int = 8
    india_crypto_require_liquidity_sweep: bool = True

    @classmethod
    def from_env(cls) -> "SessionConfig":
        return cls(
            timezone=os.getenv("SESSION_TIMEZONE", "Asia/Kolkata"),
            india_crypto_start=os.getenv("INDIA_CRYPTO_SESSION_START", "09:15"),
            india_crypto_end=os.getenv("INDIA_CRYPTO_SESSION_END", "10:30"),
            overlap_start=os.getenv("OVERLAP_SESSION_START", "18:30"),
            overlap_end=os.getenv("OVERLAP_SESSION_END", "22:30"),
            india_crypto_poll_interval_seconds=int(os.getenv("INDIA_CRYPTO_POLL_INTERVAL_SECONDS", "30")),
            overlap_poll_interval_seconds=int(os.getenv("OVERLAP_POLL_INTERVAL_SECONDS", "15")),
            idle_sleep_seconds=int(os.getenv("IDLE_SLEEP_SECONDS", "45")),
            india_crypto_min_alert_score=int(os.getenv("INDIA_CRYPTO_MIN_ALERT_SCORE", "9")),
            overlap_min_alert_score=int(os.getenv("OVERLAP_MIN_ALERT_SCORE", "8")),
            india_crypto_require_liquidity_sweep=_get_bool("INDIA_CRYPTO_REQUIRE_LIQUIDITY_SWEEP", True),
        )


@dataclass(frozen=True, slots=True)
class AppConfig:
    binance_api_key: str
    binance_secret: str
    telegram: TelegramConfig
    crypto: CryptoConfig
    sessions: SessionConfig

    @classmethod
    def load(cls) -> "AppConfig":
        load_dotenv()
        telegram = TelegramConfig.from_env()
        if not telegram.token or not telegram.chat_id:
            raise ValueError("Missing required environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID")
        return cls(
            binance_api_key=os.getenv("BINANCE_API_KEY", ""),
            binance_secret=os.getenv("BINANCE_SECRET", ""),
            telegram=telegram,
            crypto=CryptoConfig.from_env(),
            sessions=SessionConfig.from_env(),
        )
