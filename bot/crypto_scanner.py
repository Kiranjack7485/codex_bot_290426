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
        primary, confirmation = await self._fetch_symbol_context(symbol)
        signal = self.strategy.evaluate(symbol, primary, confirmation)
        return signal, {"primary": primary, "confirmation": confirmation}

    async def _fetch_symbol_context(self, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        primary, confirmation = await __import__("asyncio").gather(
            self.data_client.fetch_ohlcv(symbol, self.config.primary_timeframe, self.config.ohlcv_limit),
            self.data_client.fetch_ohlcv(symbol, self.config.confirmation_timeframe, self.config.ohlcv_limit),
        )
        return primary, confirmation
