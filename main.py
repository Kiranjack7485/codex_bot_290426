from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from bot.config import AppConfig
from bot.crypto_scanner import CryptoScanner
from bot.data_fetcher import CryptoMarketDataClient
from bot.models import CryptoSession
from bot.notifier import TelegramNotifier
from bot.reversal_engine import ReversalEngine
from bot.strategy_engine import CryptoStrategyEngine


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
LOGGER = logging.getLogger("crypto_signal_bot.main")


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    session: CryptoSession
    label: str
    poll_interval_seconds: int
    min_alert_score: int
    require_liquidity_sweep: bool


class SessionController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.timezone = ZoneInfo(config.sessions.timezone)
        self.states = {
            CryptoSession.INDIA_CRYPTO: False,
            CryptoSession.OVERLAP: False,
        }

    def evaluate(self) -> Dict[CryptoSession, str]:
        now = datetime.now(self.timezone).time()
        events: Dict[CryptoSession, str] = {}
        india_active = datetime.strptime(self.config.sessions.india_crypto_start, "%H:%M").time() <= now <= datetime.strptime(self.config.sessions.india_crypto_end, "%H:%M").time()
        overlap_active = datetime.strptime(self.config.sessions.overlap_start, "%H:%M").time() <= now <= datetime.strptime(self.config.sessions.overlap_end, "%H:%M").time()
        for session, active in {
            CryptoSession.INDIA_CRYPTO: india_active,
            CryptoSession.OVERLAP: overlap_active,
        }.items():
            if active != self.states[session]:
                self.states[session] = active
                events[session] = "start" if active else "end"
        return events

    def current_policy(self) -> Optional[SessionPolicy]:
        if self.states[CryptoSession.OVERLAP]:
            return SessionPolicy(
                session=CryptoSession.OVERLAP,
                label="US/London Overlap",
                poll_interval_seconds=self.config.sessions.overlap_poll_interval_seconds,
                min_alert_score=self.config.sessions.overlap_min_alert_score,
                require_liquidity_sweep=False,
            )
        if self.states[CryptoSession.INDIA_CRYPTO]:
            return SessionPolicy(
                session=CryptoSession.INDIA_CRYPTO,
                label="Indian Market Hours Crypto Session",
                poll_interval_seconds=self.config.sessions.india_crypto_poll_interval_seconds,
                min_alert_score=self.config.sessions.india_crypto_min_alert_score,
                require_liquidity_sweep=self.config.sessions.india_crypto_require_liquidity_sweep,
            )
        return None


async def run_bot() -> None:
    config = AppConfig.load()
    notifier = TelegramNotifier(config.telegram)
    crypto_client = CryptoMarketDataClient(config.binance_api_key, config.binance_secret)
    crypto_strategy = CryptoStrategyEngine(config.crypto)
    crypto_scanner = CryptoScanner(config.crypto, crypto_client, crypto_strategy)
    reversal_engine = ReversalEngine(crypto_strategy)
    session_controller = SessionController(config)

    await crypto_client.initialize()
    await notifier.bot_started()

    try:
        while True:
            for session, event in session_controller.evaluate().items():
                if event == "start":
                    await notifier.session_started("Indian Market Hours Crypto Session" if session == CryptoSession.INDIA_CRYPTO else "US/London Overlap")
                else:
                    reversal_engine.clear_all()
                    await notifier.session_ended("Indian Market Hours Crypto Session" if session == CryptoSession.INDIA_CRYPTO else "US/London Overlap")

            policy = session_controller.current_policy()
            if policy is None:
                await asyncio.sleep(config.sessions.idle_sleep_seconds)
                continue

            results = await asyncio.gather(*(crypto_scanner.scan_symbol(symbol) for symbol in config.crypto.symbols), return_exceptions=True)
            for symbol, result in zip(config.crypto.symbols, results):
                if isinstance(result, Exception):
                    LOGGER.error("Crypto scan failed for %s: %s", symbol, result)
                    continue
                signal, context = result
                if signal is not None:
                    if signal.score >= policy.min_alert_score and (not policy.require_liquidity_sweep or signal.components.liquidity_sweep):
                        await notifier.strong_signal(signal)
                        reversal_engine.track(signal)
                reversal = reversal_engine.crypto_reversal(symbol, context["primary"])
                if reversal is not None:
                    await notifier.reversal_alert(reversal)
            await asyncio.sleep(policy.poll_interval_seconds)
    finally:
        await crypto_client.close()


if __name__ == "__main__":
    asyncio.run(run_bot())
