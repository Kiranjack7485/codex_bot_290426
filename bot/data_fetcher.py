from __future__ import annotations

import asyncio
import logging
from typing import Dict, Tuple

import ccxt.async_support as ccxt
import pandas as pd
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from bot.config import AppConfig


LOGGER = logging.getLogger(__name__)


class BinanceFuturesDataFetcher:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.real_exchange = self._build_exchange(
            api_key=config.real_api_key,
            api_secret=config.real_api_secret,
            testnet=False,
        )
        self.testnet_exchange = self._build_exchange(
            api_key=config.testnet_api_key,
            api_secret=config.testnet_api_secret,
            testnet=True,
        )
        self.markets_loaded = False

    @staticmethod
    def _build_exchange(api_key: str, api_secret: str, testnet: bool) -> ccxt.binanceusdm:
        options = {
            "defaultType": "future",
            "adjustForTimeDifference": True,
            "fetchCurrencies": False,
        }
        exchange = ccxt.binanceusdm(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": options,
            }
        )
        if testnet:
            if hasattr(exchange, "enable_demo_trading"):
                exchange.enable_demo_trading(True)
            else:
                demo_urls = exchange.urls.get("demo")
                if demo_urls:
                    exchange.urls["api"] = demo_urls
        return exchange

    async def initialize(self) -> None:
        if self.markets_loaded:
            return
        await asyncio.gather(
            self.real_exchange.load_markets(reload=True),
            self.testnet_exchange.load_markets(reload=True),
        )
        self.markets_loaded = True
        LOGGER.info("Loaded markets for real and demo Binance Futures clients.")

    async def close(self) -> None:
        await asyncio.gather(
            self.real_exchange.close(),
            self.testnet_exchange.close(),
            return_exceptions=True,
        )

    async def validate_connections(self) -> Dict[str, str]:
        results: Dict[str, str] = {}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=3),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                if self.config.require_real_balance_auth:
                    await self.real_exchange.fetch_balance()
                    results["real"] = "private-auth-ok"
                else:
                    await self.real_exchange.fetch_time()
                    results["real"] = "public-data-ok"
                break

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=3),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                await self.testnet_exchange.fetch_balance()
                results["testnet"] = "ok"
                break

        return results

    async def fetch_ohlcv_frame(self, symbol: str, timeframe: str) -> pd.DataFrame:
        market_symbol = self._format_symbol(symbol)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                raw = await self.real_exchange.fetch_ohlcv(
                    market_symbol,
                    timeframe=timeframe,
                    limit=self.config.strategy.ohlcv_limit,
                )
                return self._to_frame(raw)
        raise RuntimeError(f"Unable to fetch OHLCV for {symbol} {timeframe}")

    async def fetch_symbol_context(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        primary, confirmation = await asyncio.gather(
            self.fetch_ohlcv_frame(symbol, self.config.strategy.primary_timeframe),
            self.fetch_ohlcv_frame(symbol, self.config.strategy.confirmation_timeframe),
        )
        return primary, confirmation

    async def fetch_account_balance(self) -> Dict:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                return await self.testnet_exchange.fetch_balance()
        raise RuntimeError("Unable to fetch testnet balance")

    async def fetch_positions(self) -> Dict:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                return await self.testnet_exchange.fetch_positions()
        raise RuntimeError("Unable to fetch open positions")

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        market_symbol = self._format_symbol(symbol)
        await self.testnet_exchange.set_leverage(leverage, market_symbol)

    @staticmethod
    def _format_symbol(symbol: str) -> str:
        return f"{symbol[:-4]}/USDT:USDT" if symbol.endswith("USDT") else symbol

    @staticmethod
    def _to_frame(raw_ohlcv: list) -> pd.DataFrame:
        frame = pd.DataFrame(
            raw_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        frame = frame.astype(
            {
                "open": "float64",
                "high": "float64",
                "low": "float64",
                "close": "float64",
                "volume": "float64",
            }
        )
        return frame
