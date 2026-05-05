from __future__ import annotations

import logging

import ccxt.async_support as ccxt
import pandas as pd
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


LOGGER = logging.getLogger(__name__)


class CryptoMarketDataClient:
    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        self.exchange = ccxt.binanceusdm(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future", "adjustForTimeDifference": True, "fetchCurrencies": False},
            }
        )
        self.markets_loaded = False

    async def initialize(self) -> None:
        if self.markets_loaded:
            return
        await self.exchange.load_markets(reload=True)
        self.markets_loaded = True
        LOGGER.info("Crypto market data client initialized.")

    async def close(self) -> None:
        await self.exchange.close()

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        market_symbol = self._format_symbol(symbol)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                raw = await self.exchange.fetch_ohlcv(market_symbol, timeframe=timeframe, limit=limit)
                frame = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
                frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
                return frame.astype({"open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"})
        return pd.DataFrame()

    @staticmethod
    def _format_symbol(symbol: str) -> str:
        return f"{symbol[:-4]}/USDT:USDT" if symbol.endswith("USDT") else symbol
