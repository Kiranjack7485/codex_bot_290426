from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bot.data_fetcher import BinanceFuturesDataFetcher
from bot.models import ActiveTrade, Direction, PositionPlan


LOGGER = logging.getLogger(__name__)


class ExecutionEngine:
    def __init__(self, data_fetcher: BinanceFuturesDataFetcher) -> None:
        self.data_fetcher = data_fetcher
        self.active_trades: Dict[str, ActiveTrade] = {}

    def list_active_trades(self) -> List[ActiveTrade]:
        return list(self.active_trades.values())

    async def sync_exchange_positions(self) -> None:
        positions = await self.data_fetcher.fetch_positions()
        current: Dict[str, ActiveTrade] = {}
        for position in positions:
            contracts = float(position.get("contracts") or position.get("positionAmt") or 0.0)
            if abs(contracts) <= 0:
                continue
            symbol = position.get("symbol", "").replace("/", "").replace(":USDT", "")
            side = Direction.LONG if contracts > 0 else Direction.SHORT
            current[symbol] = ActiveTrade(
                symbol=symbol,
                direction=side,
                quantity=abs(contracts),
                entry_price=float(position.get("entryPrice") or position.get("entry_price") or 0.0),
                stop_loss=0.0,
                take_profit=0.0,
                score=0,
                setup=None,  # type: ignore[arg-type]
                opened_at=datetime.now(timezone.utc),
                order_ids={},
            )
        self.active_trades = current

    async def execute_trade(self, plan: PositionPlan) -> Dict:
        market_symbol = self.data_fetcher._format_symbol(plan.symbol)
        market = self.data_fetcher.testnet_exchange.market(market_symbol)
        await self.data_fetcher.set_leverage(plan.symbol, plan.leverage)

        side = "buy" if plan.direction == Direction.LONG else "sell"
        reduce_side = "sell" if side == "buy" else "buy"

        if plan.entry_order_type == "market":
            entry_order = await self.data_fetcher.testnet_exchange.create_order(
                symbol=market_symbol,
                type="market",
                side=side,
                amount=plan.quantity,
            )
        else:
            entry_order = await self.data_fetcher.testnet_exchange.create_order(
                symbol=market_symbol,
                type="limit",
                side=side,
                amount=plan.quantity,
                price=self.data_fetcher.testnet_exchange.price_to_precision(market_symbol, plan.entry),
                params={"timeInForce": "GTC"},
            )
        stop_order = await self.data_fetcher.testnet_exchange.create_order(
            symbol=market_symbol,
            type="STOP_MARKET",
            side=reduce_side,
            amount=plan.quantity,
            params={
                "stopPrice": self.data_fetcher.testnet_exchange.price_to_precision(market_symbol, plan.stop_loss),
                "reduceOnly": True,
                "workingType": "MARK_PRICE",
            },
        )
        take_profit_order = await self.data_fetcher.testnet_exchange.create_order(
            symbol=market_symbol,
            type="TAKE_PROFIT_MARKET",
            side=reduce_side,
            amount=plan.quantity,
            params={
                "stopPrice": self.data_fetcher.testnet_exchange.price_to_precision(market_symbol, plan.take_profit),
                "reduceOnly": True,
                "workingType": "MARK_PRICE",
            },
        )

        self.active_trades[plan.symbol] = ActiveTrade(
            symbol=plan.symbol,
            direction=plan.direction,
            quantity=plan.quantity,
            entry_price=plan.entry,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
            score=plan.score,
            setup=plan.setup,
            opened_at=datetime.now(timezone.utc),
            order_ids={
                "entry": entry_order.get("id"),
                "stop_loss": stop_order.get("id"),
                "take_profit": take_profit_order.get("id"),
                "market_precision": market.get("precision", {}),
                "entry_type": plan.entry_order_type,
            },
        )
        LOGGER.info("Executed %s %s on testnet", plan.direction.value, plan.symbol)
        return {
            "entry_order": entry_order,
            "stop_order": stop_order,
            "take_profit_order": take_profit_order,
        }

    async def refresh_trade_state(self) -> List[Dict]:
        updates: List[Dict] = []
        to_remove: List[str] = []
        for symbol, trade in list(self.active_trades.items()):
            market_symbol = self.data_fetcher._format_symbol(symbol)
            orders = await self.data_fetcher.testnet_exchange.fetch_open_orders(market_symbol)
            order_ids = {str(order.get("id")) for order in orders}
            if str(trade.order_ids.get("stop_loss")) not in order_ids or str(trade.order_ids.get("take_profit")) not in order_ids:
                closed_orders = await self.data_fetcher.testnet_exchange.fetch_closed_orders(market_symbol, limit=10)
                close_reason = self._resolve_close_reason(trade, closed_orders)
                if close_reason:
                    updates.append(close_reason)
                    to_remove.append(symbol)
        for symbol in to_remove:
            self.active_trades.pop(symbol, None)
        return updates

    @staticmethod
    def _resolve_close_reason(trade: ActiveTrade, closed_orders: List[Dict]) -> Optional[Dict]:
        for order in closed_orders:
            order_id = str(order.get("id"))
            if order_id == str(trade.order_ids.get("take_profit")) and order.get("status") == "closed":
                return {"symbol": trade.symbol, "result": "TP", "trade": trade}
            if order_id == str(trade.order_ids.get("stop_loss")) and order.get("status") == "closed":
                return {"symbol": trade.symbol, "result": "SL", "trade": trade}
        return None
