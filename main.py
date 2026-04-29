from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from ccxt.base.errors import AuthenticationError

from bot.config import AppConfig
from bot.data_fetcher import BinanceFuturesDataFetcher
from bot.execution_engine import ExecutionEngine
from bot.notifier import TelegramNotifier
from bot.risk_manager import RiskManager
from bot.strategy_engine import StrategyEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("bot.main")


class SessionManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.timezone = ZoneInfo(config.strategy.session_timezone)
        self.states: Dict[str, bool] = {name: False for name in config.strategy.session_windows}

    def evaluate(self) -> Dict[str, str]:
        now = datetime.now(self.timezone).time()
        events: Dict[str, str] = {}
        for session_name, (start_text, end_text) in self.config.strategy.session_windows.items():
            start = datetime.strptime(start_text, "%H:%M").time()
            end = datetime.strptime(end_text, "%H:%M").time()
            active = start <= now <= end
            if active != self.states[session_name]:
                events[session_name] = "started" if active else "ended"
                self.states[session_name] = active
        return events

    def is_preferred_window(self) -> bool:
        return any(self.states.values())


async def process_symbol(
    symbol: str,
    fetcher: BinanceFuturesDataFetcher,
    strategy: StrategyEngine,
) -> Optional:
    primary, confirmation = await fetcher.fetch_symbol_context(symbol)
    return strategy.evaluate_symbol(symbol, primary, confirmation)


async def run_bot() -> None:
    config = AppConfig.load()
    fetcher = BinanceFuturesDataFetcher(config)
    notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
    strategy = StrategyEngine(config.strategy)
    risk = RiskManager(config.risk)
    execution = ExecutionEngine(fetcher)
    sessions = SessionManager(config)

    last_status_slot: Optional[int] = None
    seen_signals: Dict[str, datetime] = {}

    try:
        await fetcher.initialize()
        await fetcher.validate_connections()
        await execution.sync_exchange_positions()
        balance = await fetcher.fetch_account_balance()
        account = risk.parse_balance(balance)
        await notifier.send_startup(account.free_usdt)

        while True:
            for session_name, event in sessions.evaluate().items():
                await notifier.send_session_event(session_name, event)

            balance = await fetcher.fetch_account_balance()
            account = risk.parse_balance(balance)

            now = datetime.now(ZoneInfo(config.strategy.session_timezone))
            status_slot = now.hour * 2 + (1 if now.minute >= 30 else 0)
            if last_status_slot != status_slot and now.minute in {0, 30}:
                last_status_slot = status_slot
                await notifier.send_scan_status(len(execution.list_active_trades()), account.free_usdt)

            signals = await asyncio.gather(
                *(process_symbol(symbol, fetcher, strategy) for symbol in config.symbols),
                return_exceptions=True,
            )

            for symbol, result in zip(config.symbols, signals):
                if isinstance(result, Exception):
                    LOGGER.error("Scan failed for %s: %s", symbol, result)
                    continue
                if result is None:
                    continue

                signal_key = f"{result.symbol}:{result.direction.value}:{result.setup.value}:{result.timestamp.isoformat()}"
                if signal_key in seen_signals:
                    continue
                seen_signals[signal_key] = result.timestamp

                if result.score >= 7:
                    await notifier.send_strong_signal(result)

                can_open, reason = risk.can_open_trade(result, account, execution.list_active_trades())
                if not can_open:
                    LOGGER.info("Signal on %s rejected by risk manager: %s", result.symbol, reason)
                    continue

                if len(execution.list_active_trades()) == 1 and result.score < 8:
                    continue
                if not sessions.is_preferred_window():
                    LOGGER.info("Signal on %s skipped outside preferred trading sessions.", result.symbol)
                    continue

                market = fetcher.testnet_exchange.market(fetcher._format_symbol(result.symbol))
                plan = risk.build_position_plan(result, account, config.risk.default_leverage, market_info=market)
                await execution.execute_trade(plan)
                await notifier.send_trade_executed(plan)

            trade_updates = await execution.refresh_trade_state()
            for update in trade_updates:
                trade = update["trade"]
                await notifier.send_trade_closed(
                    symbol=trade.symbol,
                    result=update["result"],
                    entry=trade.entry_price,
                    stop_loss=trade.stop_loss,
                    take_profit=trade.take_profit,
                    score=trade.score,
                )

            await asyncio.sleep(config.scan_interval_seconds)
    except AuthenticationError as exc:
        LOGGER.error("Binance authentication failed: %s", exc)
        raise RuntimeError(
            "Binance authentication failed. Check whether the real and testnet API keys, secrets, "
            "futures permissions, and testnet environment values in .env are correct."
        ) from exc
    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(run_bot())
