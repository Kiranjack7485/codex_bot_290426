from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from bot.config import CryptoConfig
from bot.data_fetcher import CryptoMarketDataClient
from bot.models import CryptoSignal
from bot.strategy_engine import CryptoStrategyEngine


class CryptoScanner:
    def __init__(self, config: CryptoConfig, data_client: CryptoMarketDataClient, strategy: CryptoStrategyEngine) -> None:
        self.config = config
        self.data_client = data_client
        self.strategy = strategy

    async def scan_symbol(self, symbol: str) -> tuple[Optional[CryptoSignal], Dict[str, pd.DataFrame]]:
        frames = await self._fetch_symbol_context(symbol)
        signal = self.strategy.evaluate(
            symbol,
            execution_fast=frames["execution_fast"],
            execution_slow=frames["execution_slow"],
            reference_mid=frames["reference_mid"],
            reference_high=frames["reference_high"],
        )
        return signal, frames

    async def _fetch_symbol_context(self, symbol: str) -> Dict[str, pd.DataFrame]:
        execution_fast, execution_slow, reference_mid, reference_high = await __import__("asyncio").gather(
            self.data_client.fetch_ohlcv(symbol, self.config.execution_timeframes[0], self.config.ohlcv_limit),
            self.data_client.fetch_ohlcv(symbol, self.config.execution_timeframes[1], self.config.ohlcv_limit),
            self.data_client.fetch_ohlcv(symbol, self.config.reference_timeframes[0], self.config.ohlcv_limit),
            self.data_client.fetch_ohlcv(symbol, self.config.reference_timeframes[1], self.config.ohlcv_limit),
        )
        return {
            "execution_fast": execution_fast,
            "execution_slow": execution_slow,
            "reference_mid": reference_mid,
            "reference_high": reference_high,
        }
