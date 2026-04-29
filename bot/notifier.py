from __future__ import annotations

import logging
from typing import Optional

from telegram import Bot

from bot.models import PositionPlan, TradeSignal


LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send(self, message: str) -> None:
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Telegram notification failed: %s", exc)

    async def send_startup(self, capital: float) -> None:
        await self.send(
            "Bot started successfully.\n"
            "Binance Futures real/testnet login success.\n"
            f"Available capital: {capital:.2f} USDT"
        )

    async def send_scan_status(self, active_trades: int, capital: float) -> None:
        await self.send(
            "30-minute scan status.\n"
            f"Active trades: {active_trades}\n"
            f"Available capital: {capital:.2f} USDT"
        )

    async def send_session_event(self, session_name: str, event: str) -> None:
        await self.send(f"{session_name} session {event}.")

    async def send_strong_signal(self, signal: TradeSignal) -> None:
        await self.send(self._format_signal("Strong signal detected", signal))

    async def send_trade_executed(self, plan: PositionPlan) -> None:
        await self.send(
            "Demo trade executed.\n"
            f"Pair: {plan.symbol}\n"
            f"Direction: {plan.direction.value}\n"
            f"Entry: {plan.entry:.6f}\n"
            f"Stop Loss: {plan.stop_loss:.6f}\n"
            f"Take Profit: {plan.take_profit:.6f}\n"
            f"Risk/Reward: {plan.rr_ratio:.2f}\n"
            f"Confidence score: {plan.score}\n"
            f"Quantity: {plan.quantity:.6f}\n"
            f"Leverage: {plan.leverage}x\n"
            f"Entry order type: {plan.entry_order_type.upper()}"
        )

    async def send_trade_closed(self, symbol: str, result: str, entry: float, stop_loss: float, take_profit: float, score: int) -> None:
        await self.send(
            f"{result} hit.\n"
            f"Pair: {symbol}\n"
            f"Entry: {entry:.6f}\n"
            f"Stop Loss: {stop_loss:.6f}\n"
            f"Take Profit: {take_profit:.6f}\n"
            f"Confidence score: {score}"
        )

    @staticmethod
    def _format_signal(prefix: str, signal: TradeSignal) -> str:
        return (
            f"{prefix}.\n"
            f"Pair: {signal.symbol}\n"
            f"Direction: {signal.direction.value}\n"
            f"Entry: {signal.entry:.6f}\n"
            f"Stop Loss: {signal.stop_loss:.6f}\n"
            f"Take Profit: {signal.take_profit:.6f}\n"
            f"Risk/Reward: {signal.rr_ratio:.2f}\n"
            f"Confidence score: {signal.confidence_score}"
        )
