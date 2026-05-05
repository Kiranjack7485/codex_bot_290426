from __future__ import annotations

import logging
from typing import Optional

from telegram import Bot

from bot.config import TelegramConfig
from bot.models import CryptoSignal, ReversalAlert


LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, config: TelegramConfig) -> None:
        self.enabled = config.enabled
        self.chat_id = config.chat_id
        self.bot: Optional[Bot] = Bot(token=config.token) if self.enabled else None

    async def send(self, message: str) -> None:
        LOGGER.info("ALERT: %s", message.replace("\n", " | "))
        if not self.enabled or self.bot is None:
            return
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Telegram notification failed: %s", exc)

    async def bot_started(self) -> None:
        await self.send("Bot started.\nMode: SIGNAL ONLY\nMarket: CRYPTO ONLY")

    async def session_started(self, session_name: str) -> None:
        await self.send(f"Session Started\nSession: {session_name}")

    async def session_ended(self, session_name: str) -> None:
        await self.send(f"Session Ended\nSession: {session_name}")

    async def strong_signal(self, signal: CryptoSignal) -> None:
        await self.send(
            "Strong signal detected.\n"
            f"Pair: {signal.symbol}\n"
            f"Direction: {signal.direction.value}\n"
            f"Entry Zone: {signal.entry_zone[0]:.6f} - {signal.entry_zone[1]:.6f}\n"
            f"Stop Loss: {signal.stop_loss:.6f}\n"
            f"Take Profit: {signal.take_profit:.6f}\n"
            f"Risk/Reward: {signal.rr_ratio:.2f}\n"
            f"Confidence Score: {signal.confidence_score}"
        )

    async def reversal_alert(self, alert: ReversalAlert) -> None:
        await self.send(
            "Possible Trend Reversal Detected.\n"
            f"Pair: {alert.symbol}\n"
            f"Previous Direction: {alert.previous_direction.value}\n"
            f"Reason: {'; '.join(alert.reasons)}\n"
            f"Suggested Action: {alert.suggested_action}"
        )
